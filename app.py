
from flask import Flask, render_template, request, redirect, url_for
import mysql.connector
import os

app = Flask(__name__, template_folder="templates")

def get_db():
    return mysql.connector.connect(
        host="interchange.proxy.rlwy.net",
        user="root",
        password="YdcOxocVplrdfnIIFfHLSNUQGkOnDqiA",
        database="railway",
        port=53099
    )

# Homepage
@app.route("/")
def homepage():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM venues")
    venues = cursor.fetchall()
    return render_template("Homepage.html", venues=venues)

# Venue Page
@app.route("/venue/<int:venue_id>")
def venue_page(venue_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM venues WHERE id=%s", (venue_id,))
    venue = cursor.fetchone()

    return render_template("venue.html", venue=venue)

# Check available time slots
@app.route("/check_availability", methods=["POST"])
def check_availability():

    date = request.form["date"]
    venue_id = request.form["venue_id"]

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # get venue details again
    cursor.execute("SELECT * FROM venues WHERE id=%s", (venue_id,))
    venue = cursor.fetchone()

    # booked slots
    cursor.execute(
        "SELECT time_slot FROM bookings WHERE venue_id=%s AND date=%s",
        (venue_id, date)
    )
    booked = [row["time_slot"] for row in cursor.fetchall()]

    all_slots = [
        "10:00","11:00","12:00","13:00",
        "14:00","15:00","16:00","17:00",
        "18:00","19:00"
    ]

    available = [slot for slot in all_slots if slot not in booked]

    return render_template(
        "booking.html",
        venue=venue,
        venue_id=venue_id,
        date=date,
        available=available
    )
# Confirmation page
@app.route("/confirm_booking", methods=["POST"])
def confirm_booking():

    venue_id = request.form["venue_id"]
    date = request.form["date"]
    time_slot = request.form["time_slot"]

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM venues WHERE id=%s", (venue_id,))
    venue = cursor.fetchone()

    return render_template(
        "confirm.html",
        venue=venue,
        date=date,
        time_slot=time_slot
    )

# Final booking
@app.route("/book", methods=["POST"])
def book():

    venue_id = request.form["venue_id"]
    date = request.form["date"]
    time_slot = request.form["time_slot"]

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "INSERT INTO bookings (venue_id,date,time_slot) VALUES (%s,%s,%s)",
        (venue_id, date, time_slot)
    )

    db.commit()

    return redirect(url_for("my_bookings"))

# My bookings page
@app.route("/my_bookings")
def my_bookings():

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
    SELECT bookings.id, venues.name, bookings.date, bookings.time_slot
    FROM bookings
    JOIN venues ON bookings.venue_id = venues.id
    """)

    bookings = cursor.fetchall()

    return render_template("my_bookings.html", bookings=bookings)

# Delete booking
@app.route("/delete_booking/<int:id>")
def delete_booking(id):

    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM bookings WHERE id=%s", (id,))
    db.commit()

    return redirect(url_for("my_bookings"))

@app.route("/health")
def health():
    return "OK"

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5000)
