CREATE DATABASE venue_booking;
USE venue_booking;
CREATE TABLE venues(
id INT AUTO_INCREMENT PRIMARY KEY,
name VARCHAR(100),
location VARCHAR(100),
rating FLOAT,
reviews INT,
description TEXT,
image VARCHAR(255)
);
INSERT INTO venues(name, location, rating, reviews, description, image)
VALUES
('The Imperial', 'New Delhi', 9.5, 1720,
'Luxury hotel located near the central business district',
'/static/images/imperial.jpg'),

('The Leela Palace', 'New Delhi', 9.4, 1944,
'Modern luxury palace hotel with traditional architecture',
'/static/images/leela.jpg');
INSERT INTO venues (name, location, rating, reviews, description, image)
VALUES
('The Leela Palace','Bengaluru',9.4,1820,
'Luxury palace-style hotel with grand banquet halls perfect for weddings and corporate events.',
'/static/images/leela.jpg'),

('ITC Gardenia','Bengaluru',9.1,1560,
'Elegant five-star venue known for sustainable luxury and spacious conference halls.',
'/static/images/itc_gardenia.jpg'),

('Taj West End','Bengaluru',9.3,1320,
'Historic luxury hotel surrounded by lush gardens, ideal for premium events and celebrations.',
'/static/images/taj_west_end.jpg'),

('Sheraton Grand Bengaluru','Bengaluru',9.0,980,
'Modern luxury venue located at Brigade Gateway with large event halls.',
'/static/images/sheraton.jpg'),

('JW Marriott','Bengaluru',9.2,1210,
'Premium venue offering sophisticated event spaces and banquet halls.',
'/static/images/jw_marriott.jpg'),

('The Ritz Carlton','Bengaluru',9.5,1650,
'Ultra luxury venue with rooftop event spaces and elegant banquet halls.',
'/static/images/ritz_carlton.jpg');
	