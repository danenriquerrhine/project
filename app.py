from flask import Flask, render_template, request, redirect, url_for, abort, flash, session, jsonify
from datetime import datetime, date
import mysql.connector
import os
import sys
import traceback

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

def get_db():
    return mysql.connector.connect(
        host="centerbeam.proxy.rlwy.net",
        user="root",
        password="ilJEXLbQaOSmBfiwCgLaaixyVyuOgHru",
        database="railway",
        port=17244
    )

def is_venue_admin_only():
    return (session.get('is_venue_admin', False) and 
            not session.get('is_admin', False) and 
            session.get('managed_venues', []))

def get_managed_venues(user_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id FROM venues WHERE venue_admin_id = %s", (user_id,))
    venues = [row['id'] for row in cursor.fetchall()]
    cursor.close()
    db.close()
    return venues

# Helper: get available slots for a date (only approved bookings block)
def get_free_slots(venue_id, date_str):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT time_slot FROM bookings WHERE venue_id=%s AND date=%s AND status = 'approved'",
        (venue_id, date_str)
    )
    booked = [row["time_slot"] for row in cursor.fetchall()]
    cursor.close()
    db.close()
    all_slots = ["10:00","11:00","12:00","13:00","14:00","15:00","16:00","17:00","18:00","19:00"]
    return [slot for slot in all_slots if slot not in booked]

# -------------------- Routes --------------------
@app.route("/")
def homepage():
    if is_venue_admin_only():
        return redirect(url_for('venue_admin_dashboard'))
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM venues")
        venues = cursor.fetchall()
        cursor.close()
        db.close()
        return render_template("Homepage.html", venues=venues)
    except Exception as e:
        flash(f"Database error: {e}", "error")
        return render_template("Homepage.html", venues=[])

@app.route("/venue/<int:venue_id>")
def venue_page(venue_id):
    if is_venue_admin_only():
        return redirect(url_for('venue_admin_dashboard'))
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
    except Exception as e:
        flash(f"Error loading venue: {e}", "error")
        return redirect(url_for('homepage'))

@app.route("/check_availability", methods=["POST"])
def check_availability():
    if session.get('is_admin'):
        flash("Admins cannot make bookings.", "error")
        return redirect(url_for('admin_dashboard'))
    if is_venue_admin_only():
        return redirect(url_for('venue_admin_dashboard'))
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

        # Only approved bookings block the slot
        cursor.execute(
            "SELECT time_slot FROM bookings WHERE venue_id=%s AND date=%s AND status = 'approved'",
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
    except Exception as e:
        flash(f"Error checking availability: {e}", "error")
        return redirect(url_for('venue_page', venue_id=venue_id))

@app.route("/confirm_booking", methods=["POST"])
def confirm_booking():
    if session.get('is_admin'):
        flash("Admins cannot make bookings.", "error")
        return redirect(url_for('admin_dashboard'))
    if is_venue_admin_only():
        return redirect(url_for('venue_admin_dashboard'))
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
    except Exception as e:
        flash(f"Error: {e}", "error")
        return redirect(url_for('homepage'))

@app.route("/book", methods=["POST"])
def book():
    if session.get('is_admin'):
        flash("Admins cannot make bookings.", "error")
        return redirect(url_for('admin_dashboard'))
    if is_venue_admin_only():
        return redirect(url_for('venue_admin_dashboard'))
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
        db.start_transaction()

        # Check if slot is already approved
        cursor.execute(
            "SELECT COUNT(*) FROM bookings WHERE venue_id=%s AND date=%s AND time_slot=%s AND status = 'approved'",
            (venue_id, date, time_slot)
        )
        count = cursor.fetchone()[0]
        if count > 0:
            db.rollback()
            flash("Unfortunately, the time slot you have chosen is already booked, please try another time slot.", "error")
            return redirect(url_for('venue_page', venue_id=venue_id))

        # Generate new booking ID
        cursor.execute("SELECT MAX(id) FROM bookings")
        max_id = cursor.fetchone()[0]
        new_id = (max_id if max_id is not None else 0) + 1

        cursor.execute(
            "INSERT INTO bookings (id, venue_id, date, time_slot, user_id, status) VALUES (%s, %s, %s, %s, %s, %s)",
            (new_id, venue_id, date, time_slot, user_id, 'pending')
        )
        db.commit()
        flash("Booking request submitted! Awaiting admin approval.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Booking failed: {e}", "error")
    finally:
        cursor.close()
        db.close()

    return redirect(url_for("my_bookings"))

# -------------------- Edit Booking --------------------
@app.route("/edit_booking/<int:id>", methods=["GET", "POST"])
def edit_booking_form(id):
    try:
        if 'user_id' not in session:
            flash("Please log in.", "error")
            return redirect(url_for('login'))

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM bookings WHERE id = %s AND user_id = %s", (id, session['user_id']))
        booking = cursor.fetchone()
        if not booking:
            cursor.close()
            db.close()
            flash("Booking not found.", "error")
            return redirect(url_for('my_bookings'))
        if booking['status'] not in ['pending', 'rejected']:
            cursor.close()
            db.close()
            flash("Only pending or rejected bookings can be edited.", "error")
            return redirect(url_for('my_bookings'))

        cursor.execute("SELECT * FROM venues WHERE id = %s", (booking['venue_id'],))
        venue = cursor.fetchone()
        cursor.close()
        db.close()

        today = date.today().isoformat()
        selected_date = None
        slots = []
        if request.method == "POST":
            selected_date = request.form.get("date")
            if selected_date:
                try:
                    selected = datetime.strptime(selected_date, "%Y-%m-%d").date()
                    if selected < date.today():
                        flash("You cannot select a date in the past.", "error")
                    else:
                        slots = get_free_slots(booking['venue_id'], selected_date)
                except ValueError:
                    flash("Invalid date.", "error")
            else:
                flash("Please select a date.", "error")

        return render_template("edit_booking.html", booking=booking, venue=venue, today=today,
                               selected_date=selected_date, slots=slots)
    except Exception as e:
        traceback.print_exc()
        flash(f"Error loading edit form: {e}", "error")
        return redirect(url_for('my_bookings'))

@app.route("/update_booking/<int:id>", methods=["POST"])
def update_booking(id):
    try:
        if 'user_id' not in session:
            flash("Please log in.", "error")
            return redirect(url_for('login'))

        new_date = request.form["date"]
        new_time = request.form["time_slot"]

        # Validate that the new date is not in the past
        try:
            new_date_obj = datetime.strptime(new_date, "%Y-%m-%d").date()
            if new_date_obj < date.today():
                flash("You cannot select a date in the past.", "error")
                return redirect(url_for('edit_booking_form', id=id))
        except ValueError:
            flash("Invalid date.", "error")
            return redirect(url_for('edit_booking_form', id=id))

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Verify ownership and allow pending or rejected
        cursor.execute("SELECT * FROM bookings WHERE id = %s AND user_id = %s AND status IN ('pending', 'rejected')", (id, session['user_id']))
        booking = cursor.fetchone()
        if not booking:
            cursor.close()
            db.close()
            flash("Booking not found or cannot be edited.", "error")
            return redirect(url_for('my_bookings'))

        # Check if the new slot is already approved (blocked)
        cursor.execute(
            "SELECT COUNT(*) FROM bookings WHERE venue_id = %s AND date = %s AND time_slot = %s AND status = 'approved'",
            (booking['venue_id'], new_date, new_time)
        )
        count = cursor.fetchone()['COUNT(*)']
        if count > 0:
            cursor.close()
            db.close()
            flash("Unfortunately, the time slot you have chosen is already booked, please try another time slot.", "error")
            return redirect(url_for('edit_booking_form', id=id))

        # Update the booking (reset status to pending)
        cursor.execute(
            "UPDATE bookings SET date = %s, time_slot = %s, status = 'pending' WHERE id = %s",
            (new_date, new_time, id)
        )
        db.commit()
        cursor.close()
        db.close()
        flash("Booking updated and resubmitted for approval.", "success")
        return redirect(url_for('my_bookings'))
    except Exception as e:
        traceback.print_exc()
        flash(f"Error updating booking: {e}", "error")
        return redirect(url_for('my_bookings'))

@app.route("/get_available_slots")
def get_available_slots():
    venue_id = request.args.get("venue_id")
    date_str = request.args.get("date")
    if not venue_id or not date_str:
        return jsonify([])
    try:
        slots = get_free_slots(venue_id, date_str)
        return jsonify(slots)
    except Exception as e:
        print(f"Error in get_available_slots: {e}", file=sys.stderr)
        return jsonify([])

# -------------------- User Bookings --------------------
@app.route("/my_bookings")
def my_bookings():
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    if is_venue_admin_only():
        return redirect(url_for('venue_admin_dashboard'))
    if 'user_id' not in session:
        flash("Please log in to view your bookings.", "error")
        return redirect(url_for('login'))

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT bookings.id, venues.name, venues.location, bookings.date, bookings.time_slot, bookings.status
            FROM bookings
            JOIN venues ON bookings.venue_id = venues.id
            WHERE bookings.user_id = %s
            ORDER BY bookings.date DESC
        """, (session['user_id'],))
        bookings = cursor.fetchall()
        cursor.close()
        db.close()
        return render_template("my_booking.html", bookings=bookings)
    except Exception as e:
        flash(f"Error loading bookings: {e}", "error")
        return redirect(url_for('homepage'))

@app.route("/delete_booking/<int:id>")
def delete_booking(id):
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    if is_venue_admin_only():
        return redirect(url_for('venue_admin_dashboard'))
    if 'user_id' not in session:
        flash("Please log in.", "error")
        return redirect(url_for('login'))

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM bookings WHERE id=%s AND user_id=%s AND status = 'pending'", (id, session['user_id']))
        db.commit()
        if cursor.rowcount > 0:
            flash("Booking cancelled.", "success")
        else:
            flash("Cannot cancel an already approved/rejected/held booking.", "error")
        cursor.close()
        db.close()
    except Exception as e:
        flash(f"Error cancelling booking: {e}", "error")
    return redirect(url_for("my_bookings"))

# -------------------- Global Admin Routes --------------------
@app.route("/admin")
def admin_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Access denied. Admin only.", "error")
        return redirect(url_for('homepage'))

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT id, name, username, is_venue_admin FROM users")
        users = cursor.fetchall()

        cursor.execute("""
            SELECT venues.id, venues.name, venues.location, users.name as admin_name
            FROM venues
            LEFT JOIN users ON venues.venue_admin_id = users.id
            ORDER BY venues.id
        """)
        venues = cursor.fetchall()

        cursor.execute("""
            SELECT bookings.id, venues.name, venues.location, users.username, bookings.date, bookings.time_slot, bookings.status
            FROM bookings
            JOIN venues ON bookings.venue_id = venues.id
            JOIN users ON bookings.user_id = users.id
            ORDER BY bookings.date DESC, bookings.time_slot
        """)
        bookings = cursor.fetchall()

        cursor.close()
        db.close()

        return render_template("admin.html", users=users, venues=venues, bookings=bookings)
    except Exception as e:
        flash(f"Error loading admin dashboard: {e}", "error")
        return redirect(url_for('homepage'))

@app.route("/admin/update_booking/<int:id>", methods=["POST"])
def update_booking_status(id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Access denied.", "error")
        return redirect(url_for('homepage'))

    new_status = request.form.get("status")
    if new_status not in ['approved', 'rejected']:
        flash("Invalid status.", "error")
        return redirect(url_for('admin_dashboard'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Get the booking details
    cursor.execute("SELECT venue_id, date, time_slot FROM bookings WHERE id = %s", (id,))
    booking = cursor.fetchone()
    if not booking:
        cursor.close()
        db.close()
        flash("Booking not found.", "error")
        return redirect(url_for('admin_dashboard'))

    if new_status == 'approved':
        # First approve this booking
        try:
            cursor.execute("UPDATE bookings SET status = 'approved' WHERE id = %s", (id,))
            db.commit()
            flash("Booking approved.", "success")
        except Exception as e:
            db.rollback()
            flash(f"Error approving booking: {e}", "error")
            cursor.close()
            db.close()
            return redirect(url_for('admin_dashboard'))

        # Now check for other pending bookings for the same slot
        cursor.execute("""
            SELECT id FROM bookings 
            WHERE venue_id = %s AND date = %s AND time_slot = %s AND status = 'pending' AND id != %s
        """, (booking['venue_id'], booking['date'], booking['time_slot'], id))
        conflicting = cursor.fetchall()
        if conflicting:
            conflict_date = booking['date'].isoformat() if isinstance(booking['date'], date) else str(booking['date'])
            session['conflict_approved_id'] = id
            session['conflict_venue_id'] = booking['venue_id']
            session['conflict_date'] = conflict_date
            session['conflict_time'] = booking['time_slot']
            cursor.close()
            db.close()
            return redirect(url_for('admin_conflict_resolution'))
        else:
            cursor.close()
            db.close()
            return redirect(url_for('admin_dashboard'))
    else:
        # Reject
        try:
            cursor.execute("UPDATE bookings SET status = 'rejected' WHERE id = %s", (id,))
            db.commit()
            flash("Booking rejected.", "success")
        except Exception as e:
            db.rollback()
            flash(f"Error rejecting booking: {e}", "error")
        finally:
            cursor.close()
            db.close()
        return redirect(url_for('admin_dashboard'))

@app.route("/admin/conflict_resolution")
def admin_conflict_resolution():
    try:
        if 'user_id' not in session or not session.get('is_admin'):
            flash("Access denied. Admin only.", "error")
            return redirect(url_for('homepage'))

        approved_id = session.pop('conflict_approved_id', None)
        venue_id = session.pop('conflict_venue_id', None)
        date_str = session.pop('conflict_date', None)
        time_slot = session.pop('conflict_time', None)

        if not approved_id:
            flash("No pending conflict.", "error")
            return redirect(url_for('admin_dashboard'))

        # Ensure date is in YYYY-MM-DD format
        if date_str:
            try:
                if isinstance(date_str, date):
                    date_str = date_str.isoformat()
                else:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    date_str = date_obj.strftime("%Y-%m-%d")
            except Exception as e:
                print(f"Date conversion error: {e}", file=sys.stderr)

        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT bookings.id, bookings.user_id, users.name, users.username, bookings.date, bookings.time_slot, bookings.status
            FROM bookings
            JOIN users ON bookings.user_id = users.id
            WHERE bookings.venue_id = %s AND bookings.date = %s AND bookings.time_slot = %s
              AND bookings.status = 'pending' AND bookings.id != %s
        """, (venue_id, date_str, time_slot, approved_id))
        conflicting = cursor.fetchall()
        cursor.close()
        db.close()

        return render_template("admin_conflict.html", bookings=conflicting, approved_id=approved_id)
    except Exception as e:
        traceback.print_exc()
        flash(f"Error loading conflict resolution: {e}", "error")
        return redirect(url_for('admin_dashboard'))

@app.route("/admin/resolve_conflict/<int:booking_id>", methods=["POST"])
def admin_resolve_conflict(booking_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Access denied.", "error")
        return redirect(url_for('homepage'))

    action = request.form.get("action")
    if action not in ['hold', 'reject']:
        flash("Invalid action.", "error")
        return redirect(url_for('admin_dashboard'))

    new_status = 'held' if action == 'hold' else 'rejected'

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE bookings SET status = %s WHERE id = %s", (new_status, booking_id))
        db.commit()
        flash(f"Booking {new_status}.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error updating booking: {e}", "error")
    finally:
        cursor.close()
        db.close()

    return redirect(url_for('admin_dashboard'))

@app.route("/admin/assign_venue_admin", methods=["POST"])
def assign_venue_admin():
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Access denied.", "error")
        return redirect(url_for('homepage'))

    venue_id = request.form.get("venue_id")
    user_id = request.form.get("user_id")

    if not venue_id or not user_id:
        flash("Invalid venue or user.", "error")
        return redirect(url_for('admin_dashboard'))

    try:
        db = get_db()
        cursor = db.cursor()

        if user_id == '0':  # Unassign
            cursor.execute("UPDATE venues SET venue_admin_id = NULL WHERE id = %s", (venue_id,))
        else:  # Assign new admin
            cursor.execute("UPDATE venues SET venue_admin_id = %s WHERE id = %s", (user_id, venue_id))
            cursor.execute("UPDATE users SET is_venue_admin = 1 WHERE id = %s", (user_id,))
        db.commit()
        cursor.close()
        db.close()
        flash("Venue admin assigned successfully.", "success")
    except Exception as e:
        flash(f"Error assigning venue admin: {e}", "error")
    return redirect(url_for('admin_dashboard'))

@app.route("/admin/delete_booking/<int:id>")
def admin_delete_booking(id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Access denied.", "error")
        return redirect(url_for('homepage'))
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM bookings WHERE id = %s", (id,))
        db.commit()
        flash("Booking cancelled successfully.", "success")
    except Exception as e:
        flash(f"Error cancelling booking: {e}", "error")
    finally:
        cursor.close()
        db.close()
    return redirect(url_for('admin_dashboard'))

# -------------------- Venue Admin Routes --------------------
@app.route("/venue_admin")
def venue_admin_dashboard():
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    if 'user_id' not in session:
        flash("Please log in.", "error")
        return redirect(url_for('login'))

    if not session.get('is_venue_admin'):
        flash("Access denied. You are not a venue admin.", "error")
        return redirect(url_for('homepage'))

    managed_venues = session.get('managed_venues', [])
    if not managed_venues:
        flash("You are not assigned to any venue.", "error")
        return redirect(url_for('homepage'))

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        placeholders = ','.join(['%s'] * len(managed_venues))
        cursor.execute(f"""
            SELECT bookings.id, venues.name, venues.location, users.username, bookings.date, bookings.time_slot, bookings.status
            FROM bookings
            JOIN venues ON bookings.venue_id = venues.id
            JOIN users ON bookings.user_id = users.id
            WHERE venues.id IN ({placeholders})
            ORDER BY bookings.date DESC, bookings.time_slot
        """, managed_venues)
        bookings = cursor.fetchall()

        cursor.close()
        db.close()

        return render_template("venue_admin.html", bookings=bookings)
    except Exception as e:
        flash(f"Error loading venue admin dashboard: {e}", "error")
        return redirect(url_for('homepage'))

@app.route("/venue_admin/update_booking/<int:id>", methods=["POST"])
def venue_admin_update_booking(id):
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    if 'user_id' not in session or not session.get('is_venue_admin'):
        flash("Access denied.", "error")
        return redirect(url_for('homepage'))

    new_status = request.form.get("status")
    if new_status not in ['approved', 'rejected']:
        flash("Invalid status.", "error")
        return redirect(url_for('venue_admin_dashboard'))

    managed_venues = session.get('managed_venues', [])
    if not managed_venues:
        flash("Access denied.", "error")
        return redirect(url_for('homepage'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Get the booking details and verify it belongs to a managed venue
    cursor.execute("SELECT venue_id, date, time_slot FROM bookings WHERE id = %s", (id,))
    booking = cursor.fetchone()
    if not booking or booking['venue_id'] not in managed_venues:
        cursor.close()
        db.close()
        flash("You are not authorized to modify this booking.", "error")
        return redirect(url_for('venue_admin_dashboard'))

    if new_status == 'approved':
        # First approve this booking
        try:
            cursor.execute("UPDATE bookings SET status = 'approved' WHERE id = %s", (id,))
            db.commit()
            flash("Booking approved.", "success")
        except Exception as e:
            db.rollback()
            flash(f"Error approving booking: {e}", "error")
            cursor.close()
            db.close()
            return redirect(url_for('venue_admin_dashboard'))

        # Now check for other pending bookings for the same slot
        cursor.execute("""
            SELECT id FROM bookings 
            WHERE venue_id = %s AND date = %s AND time_slot = %s AND status = 'pending' AND id != %s
        """, (booking['venue_id'], booking['date'], booking['time_slot'], id))
        conflicting = cursor.fetchall()
        if conflicting:
            conflict_date = booking['date'].isoformat() if isinstance(booking['date'], date) else str(booking['date'])
            session['venue_admin_conflict_approved_id'] = id
            session['venue_admin_conflict_venue_id'] = booking['venue_id']
            session['venue_admin_conflict_date'] = conflict_date
            session['venue_admin_conflict_time'] = booking['time_slot']
            cursor.close()
            db.close()
            return redirect(url_for('venue_admin_conflict_resolution'))
        else:
            cursor.close()
            db.close()
            return redirect(url_for('venue_admin_dashboard'))
    else:
        # Reject
        try:
            cursor.execute("UPDATE bookings SET status = 'rejected' WHERE id = %s", (id,))
            db.commit()
            flash("Booking rejected.", "success")
        except Exception as e:
            db.rollback()
            flash(f"Error rejecting booking: {e}", "error")
        finally:
            cursor.close()
            db.close()
        return redirect(url_for('venue_admin_dashboard'))

@app.route("/venue_admin/conflict_resolution")
def venue_admin_conflict_resolution():
    try:
        if session.get('is_admin'):
            return redirect(url_for('admin_dashboard'))
        if 'user_id' not in session or not session.get('is_venue_admin'):
            flash("Access denied.", "error")
            return redirect(url_for('homepage'))

        approved_id = session.pop('venue_admin_conflict_approved_id', None)
        venue_id = session.pop('venue_admin_conflict_venue_id', None)
        date_str = session.pop('venue_admin_conflict_date', None)
        time_slot = session.pop('venue_admin_conflict_time', None)

        if not approved_id:
            flash("No pending conflict.", "error")
            return redirect(url_for('venue_admin_dashboard'))

        # Ensure date is in YYYY-MM-DD format
        if date_str:
            try:
                if isinstance(date_str, date):
                    date_str = date_str.isoformat()
                else:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    date_str = date_obj.strftime("%Y-%m-%d")
            except Exception as e:
                print(f"Date conversion error: {e}", file=sys.stderr)

        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT bookings.id, bookings.user_id, users.name, users.username, bookings.date, bookings.time_slot, bookings.status
            FROM bookings
            JOIN users ON bookings.user_id = users.id
            WHERE bookings.venue_id = %s AND bookings.date = %s AND bookings.time_slot = %s
              AND bookings.status = 'pending' AND bookings.id != %s
        """, (venue_id, date_str, time_slot, approved_id))
        conflicting = cursor.fetchall()
        cursor.close()
        db.close()

        return render_template("venue_admin_conflict.html", bookings=conflicting, approved_id=approved_id)
    except Exception as e:
        traceback.print_exc()
        flash(f"Error loading conflict resolution: {e}", "error")
        return redirect(url_for('venue_admin_dashboard'))

@app.route("/venue_admin/resolve_conflict/<int:booking_id>", methods=["POST"])
def venue_admin_resolve_conflict(booking_id):
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    if 'user_id' not in session or not session.get('is_venue_admin'):
        flash("Access denied.", "error")
        return redirect(url_for('homepage'))

    action = request.form.get("action")
    if action not in ['hold', 'reject']:
        flash("Invalid action.", "error")
        return redirect(url_for('venue_admin_dashboard'))

    new_status = 'held' if action == 'hold' else 'rejected'

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE bookings SET status = %s WHERE id = %s", (new_status, booking_id))
        db.commit()
        flash(f"Booking {new_status}.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error updating booking: {e}", "error")
    finally:
        cursor.close()
        db.close()

    return redirect(url_for('venue_admin_dashboard'))

@app.route("/venue_admin/delete_booking/<int:id>")
def venue_admin_delete_booking(id):
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    if 'user_id' not in session or not session.get('is_venue_admin'):
        flash("Access denied.", "error")
        return redirect(url_for('homepage'))
    
    managed_venues = session.get('managed_venues', [])
    if not managed_venues:
        flash("Access denied.", "error")
        return redirect(url_for('homepage'))
    
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        
        placeholders = ','.join(['%s'] * len(managed_venues))
        cursor.execute(f"""
            SELECT b.id FROM bookings b
            JOIN venues v ON b.venue_id = v.id
            WHERE b.id = %s AND v.id IN ({placeholders})
        """, (id,) + tuple(managed_venues))
        if not cursor.fetchone():
            flash("You are not authorized to cancel this booking.", "error")
            cursor.close()
            db.close()
            return redirect(url_for('venue_admin_dashboard'))
        
        cursor.execute("DELETE FROM bookings WHERE id = %s", (id,))
        db.commit()
        flash("Booking cancelled successfully.", "success")
        cursor.close()
        db.close()
    except Exception as e:
        flash(f"Error cancelling booking: {e}", "error")
    return redirect(url_for('venue_admin_dashboard'))

# -------------------- Authentication --------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        try:
            db = get_db()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
            user = cursor.fetchone()
            cursor.close()
            db.close()

            if user and user.get('password') == password:
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['name'] = user['name']
                session['is_admin'] = user.get('is_admin', 0)
                session['is_venue_admin'] = user.get('is_venue_admin', 0)

                if session['is_venue_admin']:
                    session['managed_venues'] = get_managed_venues(user['id'])

                flash("Logged in successfully.", "success")
                next_page = request.args.get('next')
                if next_page and next_page.startswith('/'):
                    return redirect(next_page)
                if session['is_admin']:
                    return redirect(url_for('admin_dashboard'))
                if session['is_venue_admin'] and session.get('managed_venues'):
                    return redirect(url_for('venue_admin_dashboard'))
                return redirect(url_for('homepage'))
            else:
                flash("Invalid username or password.", "error")
        except Exception as e:
            flash(f"Login error: {e}", "error")
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        username = request.form["username"]
        phone = request.form["phone"]
        password = request.form["password"]

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return redirect(url_for('signup'))
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/~`" for c in password):
            flash("Password must contain at least one special character.", "error")
            return redirect(url_for('signup'))

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
                "INSERT INTO users (id, name, username, phone, password, is_admin, is_venue_admin) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (new_id, name, username, phone, password, 0, 0)
            )
            db.commit()
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for('login'))
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
