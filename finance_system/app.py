from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from datetime import datetime, date
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.jinja_env.add_extension('jinja2.ext.do')
DATABASE = 'hr_system.db'

# 权限等级映射
ROLE_HIERARCHY = {
    '管理员': 100,
    '领导': 80,
    '主管': 60,
    '组长': 50,
    '普通职员': 30,
    '实习生': 20
}


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def login_required(f):
    """登录验证装饰器"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def role_required(min_role):
    """角色权限装饰器"""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_role' not in session:
                return redirect(url_for('login'))
            if ROLE_HIERARCHY.get(session['user_role'], 0) < ROLE_HIERARCHY.get(min_role, 0):
                flash('权限不足，无法访问该功能！', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)

        return decorated_function

    return decorator


@app.context_processor
def inject_today():
    """注入全局日期变量"""
    return {
        'today': date.today().isoformat(),
        'now': datetime.now().strftime('%Y-%m-%dT%H:%M')
    }


@app.context_processor
def utility_processor():
    """注册模板工具函数"""
    return dict(get_db=get_db)


@app.route('/')
@login_required
def dashboard():
    """工作台首页"""
    conn = get_db()

    # 统计数据
    stats = conn.execute('''
        SELECT 
            (SELECT COUNT(*) FROM employees) as total_employees,
            (SELECT COUNT(*) FROM departments) as total_departments,
            (SELECT COUNT(*) FROM positions) as total_positions,
            (SELECT COUNT(*) FROM attendance WHERE DATE(timestamp) = DATE('now')) as today_attendance,
            (SELECT COUNT(*) FROM notices WHERE is_active = 1) as active_notices
    ''').fetchone()

    # 最近入职员工
    recent_employees = conn.execute('''
        SELECT e.*, d.name as dept_name, p.title as pos_title
        FROM employees e
        LEFT JOIN departments d ON e.department_id = d.id
        LEFT JOIN positions p ON e.position_id = p.id
        ORDER BY e.join_date DESC
        LIMIT 5
    ''').fetchall()

    conn.close()
    return render_template('dashboard.html', stats=stats, employees=recent_employees)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['user_role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            flash('用户名或密码错误！', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册（自动创建员工档案）"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        name = request.form['name']
        gender = request.form['gender']
        phone = request.form['phone']

        if len(password) < 6:
            flash('密码长度至少6位！', 'error')
            return render_template('register.html')

        conn = get_db()
        try:
            # 1. 创建用户账号（默认角色：实习生）
            conn.execute('INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)',
                         (username, generate_password_hash(password), email, '实习生'))

            # 2. 自动创建员工档案
            conn.execute('''
                INSERT INTO employees (name, gender, phone, email, role, join_date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, gender, phone, email, '实习生', date.today().isoformat()))

            conn.commit()
            flash('注册成功，自动创建员工档案！', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('用户名或邮箱已存在！', 'error')
        finally:
            conn.close()
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    """用户登出"""
    session.clear()
    return redirect(url_for('login'))


@app.route('/employees', methods=['GET', 'POST'])
@login_required
def employees():
    """员工管理"""
    conn = get_db()

    if request.method == 'POST':
        name = request.form['name']
        gender = request.form['gender']
        phone = request.form['phone']
        email = request.form['emp_email']
        department_id = request.form['department_id'] or None
        position_id = request.form['position_id'] or None
        manager_id = request.form['manager_id'] or None
        role = request.form['role']
        join_date = request.form['join_date']

        conn.execute('''
            INSERT INTO employees (name, gender, phone, email, department_id, position_id, manager_id, role, join_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, gender, phone, email, department_id, position_id, manager_id, role, join_date))
        conn.commit()
        flash('员工添加成功！', 'success')
        return redirect(url_for('employees'))

    # 修复查询逻辑：管理员能看到所有员工（包括无上级员工）
    if session.get('user_role') == '管理员':
        employees = conn.execute('''
            SELECT e.*, d.name as dept_name, p.title as pos_title, m.name as manager_name
            FROM employees e
            LEFT JOIN departments d ON e.department_id = d.id
            LEFT JOIN positions p ON e.position_id = p.id
            LEFT JOIN employees m ON e.manager_id = m.id
            ORDER BY e.created_at DESC
        ''').fetchall()
    else:
        # 非管理员：查看自己管理的下属
        current_user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        current_employee = conn.execute('SELECT id FROM employees WHERE email = ?', (current_user['email'],)).fetchone()

        if current_employee:
            employees = conn.execute('''
                SELECT e.*, d.name as dept_name, p.title as pos_title, m.name as manager_name
                FROM employees e
                LEFT JOIN departments d ON e.department_id = d.id
                LEFT JOIN positions p ON e.position_id = p.id
                LEFT JOIN employees m ON e.manager_id = m.id
                WHERE e.manager_id = ?
                ORDER BY e.created_at DESC
            ''', (current_employee['id'],)).fetchall()
        else:
            employees = []

    departments = conn.execute('SELECT * FROM departments ORDER BY name').fetchall()
    positions = conn.execute('SELECT * FROM positions ORDER BY title').fetchall()

    # 获取可分配的上级
    managers = conn.execute('''
        SELECT e.*, d.name as dept_name, p.title as pos_title
        FROM employees e
        LEFT JOIN departments d ON e.department_id = d.id
        LEFT JOIN positions p ON e.position_id = p.id
        WHERE e.role IN ('领导', '主管', '组长')
        ORDER BY e.name
    ''').fetchall()

    conn.close()
    return render_template('employees.html', employees=employees, departments=departments,
                           positions=positions, managers=managers, roles=ROLE_HIERARCHY)


@app.route('/employees/delete/<int:id>')
@login_required
def delete_employee(id):
    """删除员工"""
    conn = get_db()

    # 检查是否有下属
    sub_count = conn.execute('SELECT COUNT(*) as cnt FROM employees WHERE manager_id = ?', (id,)).fetchone()['cnt']
    if sub_count > 0:
        flash('该员工有下属，请先调整下属关系！', 'error')
        conn.close()
        return redirect(url_for('employees'))

    conn.execute('DELETE FROM employees WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('员工删除成功！', 'success')
    return redirect(url_for('employees'))


@app.route('/employees/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_employee(id):
    """编辑员工（角色和上级）- 修复：同步更新users表"""
    conn = get_db()

    if request.method == 'POST':
        role = request.form['role']
        manager_id = request.form['manager_id'] or None

        # 关键修复：同时更新employees和users表
        try:
            conn.execute('BEGIN TRANSACTION')

            # 1. 更新employees表
            conn.execute('''
                UPDATE employees SET role = ?, manager_id = ? WHERE id = ?
            ''', (role, manager_id, id))

            # 2. 获取该员工的邮箱
            emp = conn.execute('SELECT email FROM employees WHERE id = ?', (id,)).fetchone()
            if emp:
                # 3. 同步更新users表（核心修复）
                conn.execute('UPDATE users SET role = ? WHERE email = ?', (role, emp['email']))

            conn.commit()
            flash('员工信息修改成功！（角色已同步到用户账号）', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'修改失败：{str(e)}', 'error')
        finally:
            conn.close()

        return redirect(url_for('employees'))

    # 获取员工信息
    employee = conn.execute('SELECT * FROM employees WHERE id = ?', (id,)).fetchone()
    if not employee:
        flash('员工不存在！', 'error')
        return redirect(url_for('employees'))

    # 获取可选上级
    managers = conn.execute('''
        SELECT e.*, d.name as dept_name, p.title as pos_title
        FROM employees e
        LEFT JOIN departments d ON e.department_id = d.id
        LEFT JOIN positions p ON e.position_id = p.id
        WHERE e.role IN ('领导', '主管', '组长')
        ORDER BY e.name
    ''').fetchall()

    conn.close()
    return render_template('edit_employee.html', employee=employee, managers=managers, roles=ROLE_HIERARCHY)


@app.route('/departments', methods=['GET', 'POST'])
@login_required
@role_required('管理员')
def departments():
    """部门管理"""
    conn = get_db()

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']

        try:
            conn.execute('INSERT INTO departments (name, description) VALUES (?, ?)', (name, description))
            conn.commit()
            flash('部门添加成功！', 'success')
        except sqlite3.IntegrityError:
            flash('部门已存在！', 'error')
        return redirect(url_for('departments'))

    departments = conn.execute('''
        SELECT d.*, COUNT(e.id) as emp_count
        FROM departments d
        LEFT JOIN employees e ON d.id = e.department_id
        GROUP BY d.id
        ORDER BY d.name
    ''').fetchall()
    conn.close()
    return render_template('departments.html', departments=departments)


@app.route('/departments/delete/<int:id>')
@login_required
@role_required('管理员')
def delete_department(id):
    """删除部门"""
    conn = get_db()
    count = conn.execute('SELECT COUNT(*) as cnt FROM employees WHERE department_id = ?', (id,)).fetchone()['cnt']
    if count == 0:
        conn.execute('DELETE FROM departments WHERE id = ?', (id,))
        conn.commit()
        flash('部门删除成功！', 'success')
    else:
        flash('该部门下有员工，无法删除！', 'error')
    conn.close()
    return redirect(url_for('departments'))


@app.route('/positions', methods=['GET', 'POST'])
@login_required
@role_required('管理员')
def positions():
    """职位管理"""
    conn = get_db()

    if request.method == 'POST':
        title = request.form['title']
        level = request.form['level']
        description = request.form['description']

        try:
            conn.execute('INSERT INTO positions (title, level, description) VALUES (?, ?, ?)',
                         (title, level, description))
            conn.commit()
            flash('职位添加成功！', 'success')
        except sqlite3.IntegrityError:
            flash('职位已存在！', 'error')
        return redirect(url_for('positions'))

    positions = conn.execute('SELECT * FROM positions ORDER BY title').fetchall()
    conn.close()
    return render_template('positions.html', positions=positions)


@app.route('/positions/delete/<int:id>')
@login_required
@role_required('管理员')
def delete_position(id):
    """删除职位"""
    conn = get_db()
    count = conn.execute('SELECT COUNT(*) as cnt FROM employees WHERE position_id = ?', (id,)).fetchone()['cnt']
    if count == 0:
        conn.execute('DELETE FROM positions WHERE id = ?', (id,))
        conn.commit()
        flash('职位删除成功！', 'success')
    else:
        flash('该职位下有员工，无法删除！', 'error')
    conn.close()
    return redirect(url_for('positions'))


@app.route('/attendance', methods=['GET', 'POST'])
@login_required
def attendance():
    """考勤管理"""
    conn = get_db()

    if request.method == 'POST':
        employee_id = request.form['employee_id']
        att_type = request.form['type']
        timestamp = request.form['timestamp']

        conn.execute('INSERT INTO attendance (employee_id, type, timestamp) VALUES (?, ?, ?)',
                     (employee_id, att_type, timestamp))
        conn.commit()
        flash('考勤记录添加成功！', 'success')
        return redirect(url_for('attendance'))

    attendance = conn.execute('''
        SELECT a.*, e.name as emp_name
        FROM attendance a
        JOIN employees e ON a.employee_id = e.id
        ORDER BY a.timestamp DESC
    ''').fetchall()

    employees = conn.execute('SELECT id, name FROM employees ORDER BY name').fetchall()
    conn.close()
    return render_template('attendance.html', attendance=attendance, employees=employees)


@app.route('/salaries', methods=['GET', 'POST'])
@login_required
def salaries():
    """薪资管理"""
    conn = get_db()

    if request.method == 'POST':
        employee_id = request.form['employee_id']
        base_salary = float(request.form['base_salary'])
        bonus = float(request.form['bonus'] or 0)
        deduction = float(request.form['deduction'] or 0)
        pay_date = request.form['pay_date']

        total = base_salary + bonus - deduction

        conn.execute('''
            INSERT INTO salaries (employee_id, base_salary, bonus, deduction, total, pay_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (employee_id, base_salary, bonus, deduction, total, pay_date))
        conn.commit()
        flash('薪资记录添加成功！', 'success')
        return redirect(url_for('salaries'))

    salaries = conn.execute('''
        SELECT s.*, e.name as emp_name
        FROM salaries s
        JOIN employees e ON s.employee_id = e.id
        ORDER BY s.pay_date DESC
    ''').fetchall()

    employees = conn.execute('SELECT id, name FROM employees ORDER BY name').fetchall()
    conn.close()
    return render_template('salaries.html', salaries=salaries, employees=employees)


@app.route('/notices', methods=['GET', 'POST'])
@login_required
@role_required('领导')
def notices():
    """通知管理"""
    conn = get_db()

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        priority = request.form['priority']

        conn.execute('''
            INSERT INTO notices (title, content, author_id, priority, is_active)
            VALUES (?, ?, ?, ?, 1)
        ''', (title, content, session['user_id'], priority))
        conn.commit()
        flash('通知发布成功！', 'success')
        return redirect(url_for('notices'))

    # 获取当前用户发布的通知
    if session.get('user_role') == '管理员':
        notices = conn.execute('''
            SELECT n.*, u.username as author_name
            FROM notices n
            JOIN users u ON n.author_id = u.id
            ORDER BY n.created_at DESC
        ''').fetchall()
    else:
        notices = conn.execute('''
            SELECT n.*, u.username as author_name
            FROM notices n
            JOIN users u ON n.author_id = u.id
            WHERE n.author_id = ?
            ORDER BY n.created_at DESC
        ''', (session['user_id'],)).fetchall()

    conn.close()
    return render_template('notices.html', notices=notices)


@app.route('/notices/delete/<int:id>')
@login_required
def delete_notice(id):
    """删除通知"""
    conn = get_db()
    notice = conn.execute('SELECT * FROM notices WHERE id = ?', (id,)).fetchone()

    if not notice:
        flash('通知不存在！', 'error')
        return redirect(url_for('notices'))

    if session.get('user_role') != '管理员' and notice['author_id'] != session['user_id']:
        flash('只能删除自己发布的通知！', 'error')
        return redirect(url_for('notices'))

    conn.execute('DELETE FROM notices WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('通知删除成功！', 'success')
    return redirect(url_for('notices'))


@app.route('/api/subordinates/<int:manager_id>')
@login_required
def get_subordinates(manager_id):
    """获取下属列表 API"""
    conn = get_db()
    subordinates = conn.execute('''
        SELECT e.id, e.name, d.name as dept_name, p.title as pos_title
        FROM employees e
        LEFT JOIN departments d ON e.department_id = d.id
        LEFT JOIN positions p ON e.position_id = p.id
        WHERE e.manager_id = ?
        ORDER BY e.name
    ''', (manager_id,)).fetchall()
    conn.close()

    return jsonify([dict(row) for row in subordinates])


if __name__ == '__main__':
    app.run(debug=True)
