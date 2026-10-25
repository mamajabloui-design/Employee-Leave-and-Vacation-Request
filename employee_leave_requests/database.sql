CREATE DATABASE IF NOT EXISTS leave_db;
USE leave_db;

-- 1. Users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    emp_code VARCHAR(20) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role ENUM('Employee', 'Admin') DEFAULT 'Employee',
    department VARCHAR(50) DEFAULT 'General',
    position VARCHAR(50) DEFAULT 'Staff',
    vacation_balance INT DEFAULT 15,
    sick_balance INT DEFAULT 10,
    reset_token VARCHAR(100) DEFAULT NULL,
    token_expiry DATETIME DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Leave Requests table
CREATE TABLE IF NOT EXISTS leave_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    leave_type ENUM('Vacation', 'Sick Leave', 'Emergency', 'Personal', 'Maternity/Paternity') NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    total_days INT NOT NULL,
    reason TEXT NOT NULL,
    status ENUM('Pending', 'Approved', 'Rejected') DEFAULT 'Pending',
    admin_remark TEXT DEFAULT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP NULL DEFAULT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Default Accounts
INSERT INTO users (emp_code, full_name, email, password, role, department, position) 
VALUES 
('ADM001', 'System Administrator', 'admin@company.com', 'adminpassword', 'Admin', 'HR', 'HR Manager'),
('EMP001', 'John Doe', 'employee@company.com', 'employeepassword', 'Employee', 'Engineering', 'Software Developer');