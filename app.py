from flask import Flask, render_template, request, redirect, url_for, abort, flash, session
from datetime import datetime, date
import mysql.connector
from mysql.connector import errorcode
import os
import sys
import time

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')  # Change this!

# -------------------- Database connection with timeout --------------------
def get_db():
    try:
        conn = mysql.connector.connect(
            host="interchange.proxy.rlwy.net",
            user="root",
            password="YdcOxocVplrdfnIIFfHLSNUQGkOnDqiA",
            database="railway",
            port=53099,
            connection_timeout=10,      # seconds
            use_pure=True                # forces Python implementation (more reliable)
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}", file=sys.stderr)
        raise  # re-raise to be caught by route error handlers

# -------------------- Routes --------------------
@app.route("/")
def homepage():
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM venues")
        venues = cursor.fetchall()
        cursor.close()
        db.close()
        return render_template("Homepage.html", venues=venues)
    except mysql.connector.Error as e:
        flash(f"Database error: {e}", "error")
        print(f"Homepage DB error: {e}", file=sys.stderr)
        return render_template("Homepage.html", venues=[])
    except Exception as e:
        flash(f"Unexpected error: {e}", "error")
        print(f"Homepage error: {e}", file=sys.stderr)
        return render_template("Homepage.html", venues=[])

@app.route("/venue/<int:venue_id>")
def venue_page(venue_id):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM venues WHERE id=%s", (venue_id,))
        venue = cursor.fetchone()
        cursor.close()
        db.close()
        if not venue:
            abort(404)
        today = date.today().isoformat()
        return render_template("venue.html", venue=venue, today=today)
    except mysql.connector.Error as e:
        flash(f"Database error: {e}", "error")
        print(f"Venue page DB error: {e}", file=sys.stderr)
        return redirect(url_for('homepage'))
    except Exception as e:
        flash(f"Error loading venue: {e}", "error")
        print(f"Venue page error: {e}", file=sys.stderr)
        return redirect(url_for('homepage'))

@app.route("/check_availability", methods=["POST"])
def check_availability():
    if 'user_id' not in session:
        flash("Please log in to book a venue.", "error")
        return redirect(url_for('login', next=request.url))

    date_str = request.form["date"]
    venue_id = request.form["venue_id"]

    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if selected_date < date.today():
            flash("You cannot book a date in the past. Please select today or a future date.", "error")
            return redirect(url_for('venue_page', venue_id=venue_id))

        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM venues WHERE id=%s", (venue_id,))
        venue = cursor.fetchone()
        if not venue:
            abort(404)

        cursor.execute(
            "SELECT time_slot FROM bookings WHERE venue_id=%s AND date=%s",
            (venue_id, date_str)
        )
        booked = [row["time_slot"] for row in cursor.fetchall()]

        all_slots = ["10:00","11:00","12:00","13:00","14:00","15:00","16:00","17:00","18:00","19:00"]
        available = [slot for slot in all_slots if slot not in booked]

        cursor.close()
        db.close()

        return render_template(
            "booking.html",
            venue=venue,
            venue_id=venue_id,
            date=date_str,
            available=available
        )
    except mysql.connector.Error as e:
        flash(f"Database error: {e}", "error")
        print(f"Check availability DB error: {e}", file=sys.stderr)
        return redirect(url_for('venue_page', venue_id=venue_id))
    except Exception as e:
        flash(f"Error checking availability: {e}", "error")
        print(f"Check availability error: {e}", file=sys.stderr)
        return redirect(url_for('venue_page', venue_id=venue_id))

@app.route("/confirm_booking", methods=["POST"])
def confirm_booking():
    if 'user_id' not in session:
        flash("Please log in to continue.", "error")
        return redirect(url_for('login'))

    venue_id = request.form["venue_id"]
    date = request.form["date"]
    time_slot = request.form["time_slot"]

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM venues WHERE id=%s", (venue_id,))
        venue = cursor.fetchone()
        cursor.close()
        db.close()
        if not venue:
            abort(404)

        return render_template(
            "confirm.html",
            venue=venue,
            date=date,
            time_slot=time_slot
        )
    except mysql.connector.Error as e:
        flash(f"Database error: {e}", "error")
        print(f"Confirm booking DB error: {e}", file=sys.stderr)
        return redirect(url_for('homepage'))
    except Exception as e:
        flash(f"Error: {e}", "error")
        print(f"Confirm booking error: {e}", file=sys.stderr)
        return redirect(url_for('homepage'))

@app.route("/book", methods=["POST"])
def book():
    if 'user_id' not in session:
        flash("Please log in to book.", "error")
        return redirect(url_for('login'))

    venue_id = request.form["venue_id"]
    date = request.form["date"]
    time_slot = request.form["time_slot"]
    user_id = session['user_id']

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute("SELECT MAX(id) FROM bookings")
        max_id = cursor.fetchone()[0]
        new_id = (max_id if max_id is not None else 0) + 1

        cursor.execute(
            "INSERT INTO bookings (id, venue_id, date, time_slot, user_id) VALUES (%s, %s, %s, %s, %s)",
            (new_id, venue_id, date, time_slot, user_id)
        )
        db.commit()
        flash("Booking successful!", "success")
    except mysql.connector.IntegrityError as e:
        db.rollback()
        flash(f"This slot may already be booked: {e}", "error")
        print(f"Booking integrity error: {e}", file=sys.stderr)
    except mysql.connector.Error as e:
        db.rollback()
        flash(f"Database error: {e}", "error")
        print(f"Booking DB error: {e}", file=sys.stderr)
    except Exception as e:
        db.rollback()
        flash(f"Booking failed: {e}", "error")
        print(f"Booking error: {e}", file=sys.stderr)
    finally:
        cursor.close()
        db.close()

    return redirect(url_for("my_bookings"))

@app.route("/my_bookings")
def my_bookings():
    if 'user_id' not in session:
        flash("Please log in to view your bookings.", "error")
        return redirect(url_for('login'))

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT bookings.id, venues.name, venues.location, bookings.date, bookings.time_slot
            FROM bookings
            JOIN venues ON bookings.venue_id = venues.id
            WHERE bookings.user_id = %s
        """, (session['user_id'],))
        bookings = cursor.fetchall()
        cursor.close()
        db.close()
        return render_template("my_booking.html", bookings=bookings)
    except mysql.connector.Error as e:
        flash(f"Database error: {e}", "error")
        print(f"My bookings DB error: {e}", file=sys.stderr)
        return redirect(url_for('homepage'))
    except Exception as e:
        flash(f"Error loading bookings: {e}", "error")
        print(f"My bookings error: {e}", file=sys.stderr)
        return redirect(url_for('homepage'))

@app.route("/delete_booking/<int:id>")
def delete_booking(id):
    if 'user_id' not in session:
        flash("Please log in.", "error")
        return redirect(url_for('login'))

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM bookings WHERE id=%s AND user_id=%s", (id, session['user_id']))
        db.commit()
        cursor.close()
        db.close()
        flash("Booking cancelled.", "success")
    except mysql.connector.Error as e:
        flash(f"Database error: {e}", "error")
        print(f"Delete booking DB error: {e}", file=sys.stderr)
    except Exception as e:
        flash(f"Error cancelling booking: {e}", "error")
        print(f"Delete booking error: {e}", file=sys.stderr)
    return redirect(url_for("my_bookings"))

# -------------------- Authentication --------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        try:
            db = get_db()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
            user = cursor.fetchone()
            cursor.close()
            db.close()

            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['name'] = user['name']
                flash("Logged in successfully.", "success")
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('homepage'))
            else:
                flash("Username not found. Please sign up.", "error")
        except mysql.connector.Error as e:
            flash(f"Database error: {e}", "error")
            print(f"Login DB error: {e}", file=sys.stderr)
        except Exception as e:
            flash(f"Login error: {e}", "error")
            print(f"Login error: {e}", file=sys.stderr)
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        username = request.form["username"]
        phone = request.form["phone"]

        if not name or not username or not phone:
            flash("All fields are required.", "error")
            return redirect(url_for('signup'))

        db = None
        cursor = None
        try:
            db = get_db()
            cursor = db.cursor(dictionary=True)

            cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
            if cursor.fetchone():
                flash("Username already taken. Choose another.", "error")
                return redirect(url_for('signup'))

            cursor.execute("SELECT MAX(id) AS max_id FROM users")
            row = cursor.fetchone()
            max_id = row['max_id'] if row and row['max_id'] is not None else 0
            new_id = max_id + 1

            cursor.execute(
                "INSERT INTO users (id, name, username, phone) VALUES (%s, %s, %s, %s)",
                (new_id, name, username, phone)
            )
            db.commit()
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError as e:
            if db:
                db.rollback()
            flash(f"Username already exists or database error: {e}", "error")
            print(f"Signup integrity error: {e}", file=sys.stderr)
        except mysql.connector.Error as e:
            if db:
                db.rollback()
            flash(f"Database error: {e}", "error")
            print(f"Signup DB error: {e}", file=sys.stderr)
        except Exception as e:
            if db:
                db.rollback()
            flash(f"Signup failed: {e}", "error")
            print(f"Signup error: {e}", file=sys.stderr)
        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()
    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('homepage'))

@app.route("/health")
def health():
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=port)
