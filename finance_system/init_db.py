import sqlite3
from werkzeug.security import generate_password_hash

DATABASE = 'hr_system.db'


def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # 1. 先创建所有表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(100) NOT NULL,
            email VARCHAR(100),
            role VARCHAR(20) DEFAULT '普通职员',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(50) UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(50) UNIQUE NOT NULL,
            level VARCHAR(20),
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(50) NOT NULL,
            gender VARCHAR(10),
            phone VARCHAR(20),
            email VARCHAR(100),
            department_id INTEGER,
            position_id INTEGER,
            manager_id INTEGER,
            role VARCHAR(20) DEFAULT '普通职员',
            join_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL,
            FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE SET NULL,
            FOREIGN KEY (manager_id) REFERENCES employees(id) ON DELETE SET NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            type VARCHAR(20) NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS salaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            base_salary DECIMAL(10,2) NOT NULL,
            bonus DECIMAL(10,2) DEFAULT 0,
            deduction DECIMAL(10,2) DEFAULT 0,
            total DECIMAL(10,2) NOT NULL,
            pay_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(100) NOT NULL,
            content TEXT NOT NULL,
            author_id INTEGER NOT NULL,
            priority VARCHAR(20) DEFAULT 'normal',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # 2. 创建所有索引（在表创建之后）
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_employees_dept ON employees(department_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_employees_pos ON employees(position_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_employees_manager ON employees(manager_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_emp ON attendance(employee_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_salaries_emp ON salaries(employee_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_notices_author ON notices(author_id)')

    # 3. 插入默认数据
    cursor.execute("INSERT OR IGNORE INTO departments (name, description) VALUES ('人事部', '负责公司人事管理')")
    cursor.execute("INSERT OR IGNORE INTO departments (name, description) VALUES ('技术部', '负责技术开发')")
    cursor.execute("INSERT OR IGNORE INTO departments (name, description) VALUES ('市场部', '负责市场营销')")

    cursor.execute("INSERT OR IGNORE INTO positions (title, level) VALUES ('经理', 'M1')")
    cursor.execute("INSERT OR IGNORE INTO positions (title, level) VALUES ('主管', 'M2')")
    cursor.execute("INSERT OR IGNORE INTO positions (title, level) VALUES ('组长', 'L1')")
    cursor.execute("INSERT OR IGNORE INTO positions (title, level) VALUES ('员工', 'E1')")

    # 4. 创建默认管理员账号
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, password, email, role)
        VALUES ('admin', ?, 'admin@company.com', '管理员')
    ''', (generate_password_hash('admin123'),))

    conn.commit()
    conn.close()
    print("数据库初始化完成！已添加默认管理员账号（admin/admin123）和基础数据。")


if __name__ == '__main__':
    init_db()