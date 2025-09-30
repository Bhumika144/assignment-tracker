from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta



# ---------------- App Setup ----------------
app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'      # replace with your email
app.config['MAIL_PASSWORD'] = 'your_app_password'         # use Gmail App Password
app.config['MAIL_DEFAULT_SENDER'] = 'your_email@gmail.com'

mail = Mail(app)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ---------------- User Class ----------------
class User(UserMixin):
    def __init__(self, id_, username, password):
        self.id = id_
        self.username = username
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        return User(user[0], user[1], user[2])
    return None




def check_achievements(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # First Assignment Completed
    c.execute("SELECT COUNT(*) FROM assignments WHERE user_id = ? AND completed = 1", (user_id,))
    completed_count = c.fetchone()[0]

    # Check if achievement already exists
    c.execute("SELECT COUNT(*) FROM achievements WHERE user_id = ? AND name = ?", (user_id, "First Assignment Completed"))
    if completed_count >= 1 and c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO achievements (user_id, name, description, date_earned) VALUES (?, ?, ?, ?)",
            (user_id, "First Assignment Completed", "Congrats on completing your first assignment!", datetime.now().strftime('%Y-%m-%d'))
        )

    c.execute("SELECT COUNT(*) FROM achievements WHERE user_id = ? AND name = ?", (user_id, "5 Assignments Completed"))
    if completed_count >= 5 and c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO achievements (user_id, name, description, date_earned) VALUES (?, ?, ?, ?)",
            (user_id, "5 Assignments Completed", "You completed 5 assignments! Keep it up!", datetime.now().strftime('%Y-%m-%d'))
        )

    conn.commit()
    conn.close()

# ---------------- Database Setup ----------------
def init_db():
    conn = sqlite3.connect('database.db')
    conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key support
    c = conn.cursor()

    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # Subjects table
    c.execute('''
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # Assignments table
    c.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            due_date TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
        )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        date_earned TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
''')

    conn.commit()
    conn.close()

# Initialize DB at startup
init_db()

# ---------------- Routes ----------------
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            flash("Account created successfully! Please login.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username already exists!", "danger")
        conn.close()

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            user_obj = User(user[0], user[1], user[2])
            login_user(user_obj)
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password!", "danger")

    return render_template('login.html')






from datetime import datetime, timedelta



@app.route('/dashboard')
@login_required
def dashboard():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Count subjects
    c.execute("SELECT COUNT(*) FROM subjects WHERE user_id = ?", (current_user.id,))
    subject_count = c.fetchone()[0]

    # Count total assignments
    c.execute("SELECT COUNT(*) FROM assignments WHERE user_id = ?", (current_user.id,))
    total_assignments = c.fetchone()[0]

    # Count completed
    c.execute("SELECT COUNT(*) FROM assignments WHERE user_id = ? AND completed = 1", (current_user.id,))
    completed_assignments = c.fetchone()[0]

    # Count pending
    c.execute("SELECT COUNT(*) FROM assignments WHERE user_id = ? AND completed = 0", (current_user.id,))
    pending_assignments = c.fetchone()[0]

    # Next upcoming assignment
    c.execute("""
        SELECT title, due_date FROM assignments 
        WHERE user_id = ? AND completed = 0 
        ORDER BY due_date ASC LIMIT 1
    """, (current_user.id,))
    upcoming = c.fetchone()

    # Assignments due soon (next 1 day)
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    c.execute("""
        SELECT title, due_date FROM assignments
        WHERE user_id = ? AND completed = 0 AND due_date <= ?
        ORDER BY due_date ASC
    """, (current_user.id, tomorrow))
    due_soon = c.fetchall()

    # Fetch user achievements
    c.execute("SELECT name, description, date_earned FROM achievements WHERE user_id = ?", (current_user.id,))
    achievements = c.fetchall()

    # Progress data for chart
    progress = {
        "completed": completed_assignments,
        "pending": pending_assignments
    }

    conn.close()

    return render_template(
        'dashboard.html',
        username=current_user.username,
        subject_count=subject_count,
        total_assignments=total_assignments,
        completed_assignments=completed_assignments,
        pending_assignments=pending_assignments,
        upcoming=upcoming,
        due_soon=due_soon,
        achievements=achievements,
        progress=progress  # <-- for chart/graph
    )




@app.route('/subjects/delete/<int:subject_id>')
@login_required
def delete_subject(subject_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # Delete subject (will also delete assignments if foreign keys are set with ON DELETE CASCADE)
    c.execute("DELETE FROM subjects WHERE id = ? AND user_id = ?", (subject_id, current_user.id))
    conn.commit()
    conn.close()
    flash("Subject deleted successfully!", "danger")
    return redirect(url_for('manage_subjects'))



@app.route('/subjects', methods=['GET', 'POST'])
@login_required
def manage_subjects():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    if request.method == 'POST':
        subject_name = request.form['name']
        c.execute("INSERT INTO subjects (user_id, name) VALUES (?, ?)", (current_user.id, subject_name))
        conn.commit()
        flash("Subject added successfully!", "success")

    c.execute("SELECT * FROM subjects WHERE user_id = ?", (current_user.id,))
    subjects_list = c.fetchall()
    conn.close()

    return render_template('subjects.html', subjects=subjects_list)







@app.route('/assignments', methods=['GET', 'POST'])
@login_required
def assignments():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Get user's subjects for dropdown
    c.execute("SELECT id, name FROM subjects WHERE user_id = ?", (current_user.id,))
    subjects = c.fetchall()

    # If POST request for adding a new assignment
    if request.method == 'POST' and 'title' in request.form:
        title = request.form['title']
        subject_id = request.form['subject_id']
        due_date = request.form['due_date']

        if not subject_id:
            flash("Please select a subject!", "danger")
        else:
            c.execute(
                "INSERT INTO assignments (user_id, subject_id, title, due_date) VALUES (?, ?, ?, ?)",
                (current_user.id, subject_id, title, due_date)
            )
            conn.commit()
            flash("Assignment added successfully!", "success")

    # Filters from form (for search/filter)
    filter_subject = request.form.get('filter_subject')
    filter_status = request.form.get('filter_status')
    search_title = request.form.get('search_title')

    # Base query
    query = '''
        SELECT a.id, a.title, a.due_date, a.completed, s.name
        FROM assignments a
        JOIN subjects s ON a.subject_id = s.id
        WHERE a.user_id = ?
    '''
    params = [current_user.id]

    # Apply subject filter
    if filter_subject and filter_subject != 'all':
        query += " AND s.id = ?"
        params.append(filter_subject)

    # Apply status filter
    if filter_status and filter_status != 'all':
        if filter_status == 'completed':
            query += " AND a.completed = 1"
        elif filter_status == 'pending':
            query += " AND a.completed = 0"

    # Apply search by title
    if search_title:
        query += " AND a.title LIKE ?"
        params.append(f"%{search_title}%")

    query += " ORDER BY a.due_date"
    c.execute(query, params)
    assignments_list = c.fetchall()
    conn.close()

    return render_template('assignments.html', assignments=assignments_list, subjects=subjects)



@app.route('/assignments/complete/<int:assignment_id>')
@login_required
def complete_assignment(assignment_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE assignments SET completed = 1 WHERE id = ? AND user_id = ?", (assignment_id, current_user.id))
    conn.commit()
    conn.close()

    # Check and award achievements
    check_achievements(current_user.id)

    flash("Assignment marked as completed!", "success")
    return redirect(url_for('assignments'))


@app.route('/assignments/pending/<int:assignment_id>')
@login_required
def pending_assignment(assignment_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE assignments SET completed = 0 WHERE id = ? AND user_id = ?", (assignment_id, current_user.id))
    conn.commit()
    conn.close()
    flash("Assignment marked as pending!", "info")
    return redirect(url_for('assignments'))

@app.route('/assignments/delete/<int:assignment_id>')
@login_required
def delete_assignment(assignment_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM assignments WHERE id = ? AND user_id = ?", (assignment_id, current_user.id))
    conn.commit()
    conn.close()
    flash("Assignment deleted successfully!", "danger")
    return redirect(url_for('assignments'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))



def send_daily_reminders():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Get all users
    c.execute("SELECT id, username FROM users")
    users = c.fetchall()
    
    for user in users:
        user_id = user[0]
        username = user[1]
        
        # Get assignments due tomorrow
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        c.execute("""
            SELECT title, due_date FROM assignments
            WHERE user_id = ? AND due_date = ? AND completed = 0
        """, (user_id, tomorrow))
        
        assignments_due = c.fetchall()
        
        if assignments_due:
            # Compose email
            body = "Hi {},\n\nYou have the following assignments due tomorrow:\n\n".format(username)
            for a in assignments_due:
                body += "- {} (Due: {})\n".format(a[0], a[1])
            body += "\nPlease complete them on time!\n\n- Student Assignment Tracker"
            
            # Send email
            try:
                msg = Message("Upcoming Assignments Reminder", recipients=[username])
                msg.body = body
                mail.send(msg)
                print(f"Reminder sent to {username}")
            except Exception as e:
                print(f"Failed to send email to {username}: {e}")
    
    conn.close()

# Start scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=send_daily_reminders, trigger="interval", hours=24)
scheduler.start()



@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    if request.method == 'POST':
        new_username = request.form['username']
        new_password = request.form['password']
        
        # Hash password if changed
        if new_password:
            hashed_password = generate_password_hash(new_password)
            c.execute("UPDATE users SET username = ?, password = ? WHERE id = ?", 
                      (new_username, hashed_password, current_user.id))
        else:
            c.execute("UPDATE users SET username = ? WHERE id = ?", 
                      (new_username, current_user.id))
        
        conn.commit()
        flash("Profile updated successfully!", "success")
        conn.close()
        return redirect(url_for('profile'))
    
    # Get current user info
    c.execute("SELECT username FROM users WHERE id = ?", (current_user.id,))
    user = c.fetchone()
    conn.close()
    
    return render_template('profile.html', username=user[0])




# ---------------- Run App ----------------
if __name__ == "__main__":
    app.run(debug=True)
