from flask import Flask, render_template, request, redirect, url_for, flash, session
import pymysql
import secrets
from functools import wraps
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'your_secret_key_here_change_in_production'

# Database Configuration for XAMPP / MySQL
DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASSWORD = ''
DB_NAME = 'leave_db'

def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

# Access Control Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'Admin':
            flash('Access denied. Administrator privileges required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Unified Authentication Routes

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password']

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
        conn.close()

        if user and user['password'] == password:
            session['user_id'] = user['id']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            flash(f'Welcome back, {user["full_name"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Password Reset Feature

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip()
        conn = get_db_connection()
        
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

            if user:
                token = secrets.token_hex(16)
                expiry = datetime.now() + timedelta(hours=1)

                cursor.execute("""
                    UPDATE users 
                    SET reset_token = %s, token_expiry = %s 
                    WHERE email = %s
                """, (token, expiry, email))
                
                reset_url = url_for('reset_password', token=token, _external=True)
                flash(f'Reset link generated for local testing: <a href="{reset_url}">Click Here to Reset Password</a>', 'info')
            else:
                flash('If that email exists in our system, a reset link has been created.', 'info')
        
        conn.close()
        return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE reset_token = %s AND token_expiry > NOW()", (token,))
        user = cursor.fetchone()

    if not user:
        conn.close()
        flash('Invalid or expired password reset token.', 'danger')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form['password']

        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE users 
                SET password = %s, reset_token = NULL, token_expiry = NULL 
                WHERE id = %s
            """, (new_password, user['id']))

        conn.close()
        flash('Your password has been successfully reset! You can now log in.', 'success')
        return redirect(url_for('login'))

    conn.close()
    return render_template('reset_password.html', token=token)

# Admin-Only Registration Portal

@app.route('/add-employee', methods=['GET', 'POST'])
@login_required
@admin_required
def add_employee():
    if request.method == 'POST':
        emp_code = request.form['emp_code'].strip()
        full_name = request.form['full_name'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        role = request.form['role']
        department = request.form['department']
        position = request.form['position']
        vacation_balance = request.form.get('vacation_balance', 15)
        sick_balance = request.form.get('sick_balance', 10)

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO users (emp_code, full_name, email, password, role, department, position, vacation_balance, sick_balance)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (emp_code, full_name, email, password, role, department, position, vacation_balance, sick_balance))
            flash(f'Account created successfully for {full_name} ({role})!', 'success')
            return redirect(url_for('add_employee'))
        except pymysql.MySQLError:
            flash('Error creating account. Employee ID or Email already exists.', 'danger')
        finally:
            conn.close()

    return render_template('add_employee.html')

# Operational Portal Routes

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    user_id = session['user_id']
    role = session['role']

    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user_info = cursor.fetchone()

        if role == 'Admin':
            cursor.execute("""
                SELECT lr.*, u.full_name, u.emp_code, u.department 
                FROM leave_requests lr
                JOIN users u ON lr.user_id = u.id
                ORDER BY lr.applied_at DESC LIMIT 10
            """)
            recent_requests = cursor.fetchall()

            cursor.execute("SELECT COUNT(*) AS count FROM leave_requests WHERE status = 'Pending'")
            pending_count = cursor.fetchone()['count']
            cursor.execute("SELECT COUNT(*) AS count FROM leave_requests WHERE status = 'Approved'")
            approved_count = cursor.fetchone()['count']
            cursor.execute("SELECT COUNT(*) AS count FROM users WHERE role = 'Employee'")
            total_employees = cursor.fetchone()['count']

            conn.close()
            return render_template('dashboard.html', user=user_info, recent_requests=recent_requests,
                                   pending_count=pending_count, approved_count=approved_count, 
                                   total_employees=total_employees)
        else:
            cursor.execute("""
                SELECT * FROM leave_requests 
                WHERE user_id = %s 
                ORDER BY applied_at DESC
            """, (user_id,))
            user_requests = cursor.fetchall()

            conn.close()
            return render_template('dashboard.html', user=user_info, requests=user_requests)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_id = session['user_id']
    conn = get_db_connection()

    if request.method == 'POST':
        full_name = request.form['full_name'].strip()
        department = request.form['department'].strip()
        position = request.form['position'].strip()
        new_password = request.form.get('new_password', '').strip()

        with conn.cursor() as cursor:
            if new_password:
                cursor.execute("""
                    UPDATE users SET full_name = %s, department = %s, position = %s, password = %s
                    WHERE id = %s
                """, (full_name, department, position, new_password, user_id))
            else:
                cursor.execute("""
                    UPDATE users SET full_name = %s, department = %s, position = %s
                    WHERE id = %s
                """, (full_name, department, position, user_id))

        session['full_name'] = full_name
        flash('Profile updated successfully!', 'success')

    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
    conn.close()

    return render_template('profile.html', user=user)

@app.route('/apply-leave', methods=['GET', 'POST'])
@login_required
def apply_leave():
    if request.method == 'POST':
        leave_type = request.form['leave_type']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason'].strip()

        d1 = datetime.strptime(start_date, '%Y-%m-%d')
        d2 = datetime.strptime(end_date, '%Y-%m-%d')
        
        if d2 < d1:
            flash('End Date cannot be before Start Date.', 'danger')
            return redirect(url_for('apply_leave'))

        total_days = (d2 - d1).days + 1

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO leave_requests (user_id, leave_type, start_date, end_date, total_days, reason)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (session['user_id'], leave_type, start_date, end_date, total_days, reason))
        conn.close()

        flash('Leave application submitted successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('apply_leave.html')

@app.route('/manage-leaves')
@login_required
@admin_required
def manage_leaves():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT lr.*, u.full_name, u.emp_code, u.department, u.vacation_balance, u.sick_balance
            FROM leave_requests lr
            JOIN users u ON lr.user_id = u.id
            ORDER BY FIELD(lr.status, 'Pending', 'Approved', 'Rejected'), lr.applied_at DESC
        """)
        requests_list = cursor.fetchall()
    conn.close()
    return render_template('manage_leaves.html', requests=requests_list)

@app.route('/review-leave/<int:request_id>/<action>', methods=['POST'])
@login_required
@admin_required
def review_leave(request_id, action):
    admin_remark = request.form.get('admin_remark', '').strip()
    status = 'Approved' if action == 'approve' else 'Rejected'

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM leave_requests WHERE id = %s", (request_id,))
        leave_req = cursor.fetchone()

        if leave_req:
            cursor.execute("""
                UPDATE leave_requests 
                SET status = %s, admin_remark = %s, reviewed_at = NOW() 
                WHERE id = %s
            """, (status, admin_remark, request_id))

            if status == 'Approved':
                user_id = leave_req['user_id']
                leave_type = leave_req['leave_type']
                days = leave_req['total_days']

                if leave_type == 'Vacation':
                    cursor.execute("UPDATE users SET vacation_balance = GREATEST(0, vacation_balance - %s) WHERE id = %s", (days, user_id))
                elif leave_type == 'Sick Leave':
                    cursor.execute("UPDATE users SET sick_balance = GREATEST(0, sick_balance - %s) WHERE id = %s", (days, user_id))

            flash(f'Leave request #{request_id} has been {status.lower()}.', 'success')
    conn.close()
    return redirect(url_for('manage_leaves'))

@app.route('/reports')
@login_required
@admin_required
def reports():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT count(*) as total FROM leave_requests")
        total = cursor.fetchone()['total']

        cursor.execute("SELECT count(*) as total FROM leave_requests WHERE status='Approved'")
        approved = cursor.fetchone()['total']

        cursor.execute("SELECT count(*) as total FROM leave_requests WHERE status='Pending'")
        pending = cursor.fetchone()['total']

        cursor.execute("SELECT count(*) as total FROM leave_requests WHERE status='Rejected'")
        rejected = cursor.fetchone()['total']

        cursor.execute("""
            SELECT leave_type, COUNT(*) as count, SUM(total_days) as days
            FROM leave_requests WHERE status = 'Approved'
            GROUP BY leave_type
        """)
        type_breakdown = cursor.fetchall()

        cursor.execute("""
            SELECT u.department, COUNT(lr.id) as total_requests
            FROM leave_requests lr
            JOIN users u ON lr.user_id = u.id
            GROUP BY u.department
        """)
        dept_breakdown = cursor.fetchall()

    conn.close()
    return render_template('reports.html', total=total, approved=approved, 
                           pending=pending, rejected=rejected, 
                           type_breakdown=type_breakdown, dept_breakdown=dept_breakdown)

if __name__ == '__main__':
    app.run(debug=True)