import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Flask App Setup ---
app = Flask(__name__)

# Configure CORS to allow requests from your frontend.
# IMPORTANT: In production, replace '*' with your actual frontend domain
# e.g., CORS(app, origins="https://www.yourartaxwebsite.com")
CORS(app) 

# --- Database Setup (PostgreSQL) ---
# Construct the PostgreSQL connection string from environment variables
# This is crucial for securely storing credentials
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_HOST = os.environ.get("DB_HOST", "localhost") # Default to localhost if not specified
DB_PORT = os.environ.get("DB_PORT", "5432")     # Default PostgreSQL port
DB_NAME = os.environ.get("DB_NAME")

if not all([DB_USER, DB_PASSWORD, DB_NAME]):
    raise ValueError("Missing database environment variables. Ensure DB_USER, DB_PASSWORD, DB_NAME are set in .env")

# PostgreSQL connection string format:
# postgresql://user:password@host:port/database_name
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
Base = declarative_base() # Base class for our models

# Define the Inquiry Model (for Contact Us form submissions)
class Inquiry(Base):
    __tablename__ = 'inquiries'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(120), nullable=False)
    phone = Column(String(20)) # Optional
    inquiry_type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow) # Use UTC time

    def __repr__(self):
        return f"<Inquiry {self.name} - {self.inquiry_type}>"

# Define a Testimonial Model (for dynamic testimonials)
class Testimonial(Base):
    __tablename__ = 'testimonials'
    id = Column(Integer, primary_key=True)
    client_name = Column(String(100), nullable=False)
    location = Column(String(100))
    quote = Column(Text, nullable=False)
    rating = Column(Integer, nullable=False) # Store rating as integer (e.g., 1-5)
    image_url = Column(String(255)) # URL to client's image (frontend responsibility)
    timestamp = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Testimonial {self.client_name} - {self.rating} stars>"

# Define a Package Model (for dynamic Wi-Fi packages)
class Package(Base):
    __tablename__ = 'packages'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(255))
    price = Column(Integer, nullable=False) # Store price in smallest currency unit (e.g., cents/shillings) or as float
    speed = Column(String(50)) # e.g., "10 Mbps"
    devices_supported = Column(String(50)) # e.g., "1-3 Devices", "Unlimited"
    features_list = Column(Text) # Store comma-separated features or JSON string
    is_popular = Column(Integer, default=0) # 1 for popular, 0 for not (Boolean in other DBs)
    
    def __repr__(self):
        return f"<Package {self.name} - {self.price}>"

    def to_dict(self):
        """Converts a Package object to a dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "speed": self.speed,
            "devices_supported": self.devices_supported,
            "features": [f.strip() for f in self.features_list.split(',')] if self.features_list else [],
            "popular": bool(self.is_popular)
        }

# Create database tables (if they don't exist)
# This will connect to PostgreSQL and create tables defined by your models
Base.metadata.create_all(engine)

# Create a session to interact with the database
Session = sessionmaker(bind=engine)

# --- API Endpoints ---

@app.route('/')
def home():
    """Simple home route to confirm the backend is running."""
    return jsonify({"message": "Artax Backend is running with PostgreSQL!"})

@app.route('/api/contact-inquiry', methods=['POST'])
def submit_contact_inquiry():
    """Endpoint for submitting the contact form."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        required_fields = ['name', 'email', 'inquiryType', 'message']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({"status": "error", "message": f"Missing required field: {field}"}), 400

        session = Session()
        try:
            new_inquiry = Inquiry(
                name=data['name'],
                email=data['email'],
                phone=data.get('phone'), # Use .get() for optional fields
                inquiry_type=data['inquiryType'],
                message=data['message']
            )
            session.add(new_inquiry)
            session.commit()
            print(f"New inquiry received from {data['name']} ({data['email']}) for {data['inquiryType']}")
            return jsonify({"status": "success", "message": "Inquiry submitted successfully!"}), 201
        except Exception as db_error:
            session.rollback() # Rollback in case of error
            print(f"Database error submitting inquiry: {db_error}")
            return jsonify({"status": "error", "message": "Failed to save inquiry to database."}), 500
        finally:
            session.close()

    except Exception as e:
        print(f"Error processing inquiry request: {e}")
        return jsonify({"status": "error", "message": "An internal server error occurred."}), 500

@app.route('/api/packages', methods=['GET'])
def get_packages():
    """Endpoint to fetch Wi-Fi packages from the database."""
    session = Session()
    try:
        packages = session.query(Package).all()
        # Convert Package objects to dictionaries for JSON serialization
        return jsonify([pkg.to_dict() for pkg in packages]), 200
    except Exception as e:
        print(f"Error fetching packages: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch packages."}), 500
    finally:
        session.close()

@app.route('/api/testimonials', methods=['GET'])
def get_testimonials():
    """Endpoint to fetch client testimonials from the database."""
    session = Session()
    try:
        testimonials = session.query(Testimonial).all()
        # Convert Testimonial objects to dictionaries for JSON serialization
        # Ensure 'image_url' matches your frontend's image paths
        return jsonify([{
            "id": t.id,
            "client_name": t.client_name,
            "location": t.location,
            "quote": t.quote,
            "rating": t.rating,
            "image": t.image_url # Frontend will use this path
        } for t in testimonials]), 200
    except Exception as e:
        print(f"Error fetching testimonials: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch testimonials."}), 500
    finally:
        session.close()

# --- Initial Data Seeding (Optional, for development) ---
@app.route('/api/seed-data', methods=['GET'])
def seed_data():
    """
    Endpoint to seed initial data into the database.
    RUN THIS ONCE AFTER SETTING UP YOUR DATABASE.
    DO NOT EXPOSE IN PRODUCTION WITHOUT AUTHENTICATION.
    """
    session = Session()
    try:
        # Clear existing data to prevent duplicates on re-seeding
        session.query(Package).delete()
        session.query(Testimonial).delete()
        session.commit()

        # Seed Packages
        packages_to_add = [
            Package(
                name="Basic Fiber",
                description="Perfect for casual users",
                price=2500, # Assuming KES 2500
                speed="Up to 10 Mbps",
                devices_supported="1-3 Devices",
                features_list="Standard Usage, No Priority Support",
                is_popular=0
            ),
            Package(
                name="Standard Fiber",
                description="Ideal for families & streaming",
                price=4000, # Assuming KES 4000
                speed="Up to 30 Mbps",
                devices_supported="4-8 Devices",
                features_list="Moderate Usage, Standard Support",
                is_popular=1
            ),
            Package(
                name="Premium Fiber",
                description="Best for heavy users & gaming",
                price=7500, # Assuming KES 7500
                speed="Up to 100 Mbps",
                devices_supported="Unlimited Devices",
                features_list="Heavy Usage, Priority 24/7 Support",
                is_popular=0
            )
        ]
        session.add_all(packages_to_add)

        # Seed Testimonials
        testimonials_to_add = [
            Testimonial(
                client_name="Sarah M.",
                location="Nairobi",
                quote="Artax transformed our home internet! Blazing fast speeds and incredibly reliable. Their team was professional and efficient. Highly recommend their fiber services.",
                rating=5,
                image_url="images/client1.jpg"
            ),
            Testimonial(
                client_name="James K.",
                location="Kakamega",
                quote="The CCTV installation by Artax gave us so much peace of mind. The quality is superb, and the remote monitoring works flawlessly. A truly professional service!",
                rating=4, # Store as integer 4 for 4.5 stars (adjust if needed)
                image_url="images/client2.jpg"
            ),
            Testimonial(
                client_name="Emily W.",
                location="Maseno",
                quote="Needed a TV mounted quickly and securely. Artax delivered beyond expectations! Clean work and friendly technicians. My living room looks fantastic now.",
                rating=5,
                image_url="images/client1.jpg"
            )
        ]
        session.add_all(testimonials_to_add)

        session.commit()
        return jsonify({"status": "success", "message": "Database seeded successfully!"}), 200
    except Exception as e:
        session.rollback()
        print(f"Error seeding data: {e}")
        return jsonify({"status": "error", "message": f"Failed to seed database: {e}"}), 500
    finally:
        session.close()


# --- Run the Flask Application ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)