from flask import Flask, render_template
import mysql.connector
import os

app = Flask(__name__)

# MySQL connection
db = mysql.connector.connect(
    host="interchange.proxy.rlwy.net",
    user="root",
    password="YdcOxocVplrdfnIIFfHLSNUQGkOnDqiA",
    database="railway",
    port= 53099
)
print("QWERTYUIOP%%%%%%%%%#############: ",os.getcwd())
# Homepage route
@app.route("/")
def homepage():

    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM venues")

    venues = cursor.fetchall()

    return render_template("homepage.html", venues=venues)

print(os.getcwd())
# Venue page route
@app.route("/venue/<int:venue_id>")
def venue_page(venue_id):

    cursor = db.cursor(dictionary=True)

    query = "SELECT * FROM venues WHERE id = %s"

    cursor.execute(query, (venue_id,))

    venue = cursor.fetchone()

    return render_template("venue.html", venue=venue)

@app.route("/health")
def health():
    return "OK"


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False,host='0.0.0.0',port=5000)
