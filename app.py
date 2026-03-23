@app.route("/venue_admin/delete_booking/<int:id>")
def venue_admin_delete_booking(id):
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
        
        # Check authorization: booking must belong to a managed venue
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
        
        # Delete the booking
        cursor.execute("DELETE FROM bookings WHERE id = %s", (id,))
        db.commit()
        flash("Booking cancelled successfully.", "success")
        cursor.close()
        db.close()
    except Exception as e:
        flash(f"Error cancelling booking: {e}", "error")
    return redirect(url_for('venue_admin_dashboard'))
