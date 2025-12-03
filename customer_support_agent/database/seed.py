"""
Database Seeder - Populate Firestore with Demo Data
=====================================================
Usage:
    python seed_database.py --project PROJECT_ID --database DATABASE_ID
    python seed_database.py --project PROJECT_ID --database DATABASE_ID --clear
"""

import argparse
from google.cloud import firestore


def get_sample_data():
    """Returns all sample data for the demo."""
    
    products = {
        "PROD-001": {
            "name": "ProBook Laptop 15", "price": 999.99, "category": "Electronics",
            "description": "High-performance laptop with Intel i7",
            "keywords": ["laptop", "computer", "notebook", "probook"],
            "specs": {"processor": "Intel Core i7-12700H", "ram": "16GB DDR5", "storage": "512GB NVMe SSD"},
            "warranty": "2 years", "rating": 4.5,
        },
        "PROD-006": {
            "name": "ROG Gaming Laptop", "price": 1499.99, "category": "Electronics",
            "description": "High-performance gaming laptop with RTX 4060 graphics card",
            "keywords": ["laptop", "gaming", "computer", "notebook", "rog", "gaming laptop"],
            "specs": {"processor": "Intel Core i7-13700H", "gpu": "NVIDIA RTX 4060", "ram": "32GB DDR5", "storage": "1TB NVMe SSD", "display": "15.6 inch 144Hz"},
            "warranty": "2 years", "rating": 4.8,
        },
        "PROD-002": {
            "name": "Wireless Headphones Pro", "price": 199.99, "category": "Electronics",
            "description": "Premium noise-canceling wireless headphones",
            "keywords": ["headphones", "audio", "wireless", "bluetooth"],
            "specs": {"driver": "40mm", "battery": "30 hours", "noise_canceling": True},
            "warranty": "1 year", "rating": 4.7,
        },
        "PROD-003": {
            "name": "Mechanical Gaming Keyboard", "price": 149.99, "category": "Electronics",
            "description": "RGB mechanical keyboard with Cherry MX switches",
            "keywords": ["keyboard", "gaming", "mechanical", "rgb"],
            "specs": {"switches": "Cherry MX Red", "layout": "Full-size", "backlighting": "RGB"},
            "warranty": "2 years", "rating": 4.6,
        },
        "PROD-004": {
            "name": "Ergonomic Office Chair", "price": 449.99, "category": "Furniture",
            "description": "Premium ergonomic chair with lumbar support",
            "keywords": ["chair", "office", "ergonomic", "furniture"],
            "specs": {"material": "Mesh back", "adjustable": "Height, armrests, lumbar"},
            "warranty": "5 years", "rating": 4.4,
        },
        "PROD-005": {
            "name": "Standing Desk Pro", "price": 599.99, "category": "Furniture",
            "description": "Electric sit-stand desk with memory presets",
            "keywords": ["desk", "standing", "office", "furniture"],
            "specs": {"dimensions": "60x30 inches", "height_range": "25-51 inches", "motor": "Dual"},
            "warranty": "10 years", "rating": 4.8,
        },
    }
    
    inventory = {
        "PROD-001": {"total_stock": 45, "warehouses": {"US-West": 20, "US-East": 15, "EU": 10}},
        "PROD-002": {"total_stock": 120, "warehouses": {"US-West": 50, "US-East": 40, "EU": 30}},
        "PROD-003": {"total_stock": 78, "warehouses": {"US-West": 30, "US-East": 28, "EU": 20}},
        "PROD-004": {"total_stock": 23, "warehouses": {"US-West": 10, "US-East": 8, "EU": 5}},
        "PROD-005": {"total_stock": 15, "warehouses": {"US-West": 8, "US-East": 5, "EU": 2}},
        "PROD-006": {"total_stock": 32, "warehouses": {"US-West": 15, "US-East": 12, "EU": 5}},
    }
    
    reviews = {
        "PROD-001": {
            "avg_rating": 4.5, "total_reviews": 234,
            "recent_reviews": [
                {"user": "TechFan", "rating": 5, "comment": "Excellent performance!"},
                {"user": "Student123", "rating": 4, "comment": "Great for coding."},
            ],
        },
        "PROD-002": {
            "avg_rating": 4.7, "total_reviews": 512,
            "recent_reviews": [
                {"user": "MusicLover", "rating": 5, "comment": "Best noise canceling!"},
                {"user": "Commuter", "rating": 5, "comment": "Perfect for travel."},
            ],
        },
        "PROD-006": {
            "avg_rating": 4.8, "total_reviews": 189,
            "recent_reviews": [
                {"user": "GamerPro", "rating": 5, "comment": "Runs all games smoothly at high settings!"},
                {"user": "Streamer99", "rating": 5, "comment": "Perfect for streaming and gaming!"},
            ],
        },
    }
    
    orders = {
        "ORD-12345": {
            "customer_id": "CUST-001", "date": "2025-01-15", "status": "In Transit",
            "carrier": "FastShip", "tracking_number": "FS789456123",
            "estimated_delivery": "2025-01-20",
            "items": [
                {"product_id": "PROD-001", "name": "ProBook Laptop 15", "qty": 1, "price": 999.99},
                {"product_id": "PROD-002", "name": "Wireless Headphones Pro", "qty": 1, "price": 199.99},
            ],
            "subtotal": 1199.98, "tax": 96.00, "total": 1295.98,
            "timeline": [
                {"date": "2025-01-15", "event": "Order placed"},
                {"date": "2025-01-16", "event": "Processing complete"},
                {"date": "2025-01-17", "event": "Shipped"},
                {"date": "2025-01-18", "event": "In transit"},
            ],
        },
        "ORD-67890": {
            "customer_id": "CUST-001", "date": "2025-01-10", "status": "Delivered",
            "carrier": "QuickPost", "tracking_number": "QP456789012", "delivered_date": "2025-01-14",
            "items": [{"product_id": "PROD-002", "name": "Wireless Headphones Pro", "qty": 1, "price": 199.99}],
            "subtotal": 199.99, "tax": 16.00, "total": 215.99,
            "timeline": [
                {"date": "2025-01-10", "event": "Order placed"},
                {"date": "2025-01-11", "event": "Shipped"},
                {"date": "2025-01-14", "event": "Delivered"},
            ],
        },
        "ORD-11111": {
            "customer_id": "CUST-001", "date": "2024-12-20", "status": "Delivered",
            "carrier": "FastShip", "delivered_date": "2024-12-24",
            "items": [{"product_id": "PROD-004", "name": "Ergonomic Office Chair", "qty": 1, "price": 449.99}],
            "subtotal": 449.99, "tax": 36.00, "total": 485.99,
            "timeline": [{"date": "2024-12-20", "event": "Order placed"}, {"date": "2024-12-24", "event": "Delivered"}],
        },
        "ORD-22222": {
            "customer_id": "CUST-002", "date": "2025-01-12", "status": "Processing",
            "items": [{"product_id": "PROD-005", "name": "Standing Desk Pro", "qty": 1, "price": 599.99}],
            "subtotal": 599.99, "tax": 48.00, "total": 647.99,
            "timeline": [{"date": "2025-01-12", "event": "Order placed"}, {"date": "2025-01-13", "event": "Processing"}],
        },
    }
    
    invoices = {
        "INV-2025-001": {
            "order_id": "ORD-12345", "customer_id": "CUST-001",
            "date": "2025-01-15", "due_date": "2025-02-15", "status": "Pending",
            "items": [
                {"description": "ProBook Laptop 15", "qty": 1, "price": 999.99},
                {"description": "Wireless Headphones Pro", "qty": 1, "price": 199.99},
            ],
            "subtotal": 1199.98, "tax": 96.00, "total": 1295.98,
        },
        "INV-2025-002": {
            "order_id": "ORD-67890", "customer_id": "CUST-001",
            "date": "2025-01-10", "status": "Paid",
            "items": [{"description": "Wireless Headphones Pro", "qty": 1, "price": 199.99}],
            "subtotal": 199.99, "tax": 16.00, "total": 215.99,
        },
    }
    
    payments = {
        "ORD-12345": {"payment_status": "Pending", "amount_due": 1295.98, "payment_method": "Credit Card (ending 4242)"},
        "ORD-67890": {"payment_status": "Completed", "amount_paid": 215.99, "payment_date": "2025-01-10", "transaction_id": "TXN-789456"},
        "ORD-11111": {"payment_status": "Completed", "amount_paid": 485.99, "payment_date": "2024-12-20", "transaction_id": "TXN-111222"},
        "ORD-22222": {"payment_status": "Completed", "amount_paid": 647.99, "payment_date": "2025-01-12", "transaction_id": "TXN-222333"},
    }
    
    refund_eligibility = {
        "ORD-12345": {"eligible": True, "reason": "Within 30-day return window", "max_refund": 1295.98},
        "ORD-67890": {"eligible": True, "reason": "Within 30-day return window", "max_refund": 215.99},
        "ORD-11111": {"eligible": False, "reason": "Past 30-day return window"},
        "ORD-22222": {"eligible": True, "reason": "Order not yet shipped - can cancel", "max_refund": 647.99},
    }
    
    customers = {
        "CUST-001": {"name": "John Doe", "email": "john.doe@example.com", "tier": "Gold"},
        "CUST-002": {"name": "Jane Smith", "email": "jane.smith@example.com", "tier": "Silver"},
    }
    
    return {
        "products": products,
        "inventory": inventory,
        "reviews": reviews,
        "orders": orders,
        "invoices": invoices,
        "payments": payments,
        "refund_eligibility": refund_eligibility,
        "customers": customers,
    }


def seed_firestore(project_id: str, database_id: str = "(default)", clear: bool = False):
    """Seed Firestore database with sample data."""
    print("=" * 60)
    print("FIRESTORE DATABASE SEEDER")
    print("=" * 60)
    print(f"Project:  {project_id}")
    print(f"Database: {database_id}")
    
    db = firestore.Client(project=project_id, database=database_id)
    data = get_sample_data()
    
    if clear:
        print("\n⚠️  Clearing existing data...")
        for collection_name in data.keys():
            docs = db.collection(collection_name).stream()
            for doc in docs:
                doc.reference.delete()
            print(f"   Cleared: {collection_name}")
    
    print("\n📦 Seeding collections...")
    for collection_name, documents in data.items():
        collection_ref = db.collection(collection_name)
        count = 0
        for doc_id, doc_data in documents.items():
            collection_ref.document(doc_id).set(doc_data)
            count += 1
        print(f"   ✓ {collection_name}: {count} documents")
    
    print("\n" + "=" * 60)
    print("✅ DATABASE SEEDING COMPLETE!")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Seed Firestore with demo data")
    parser.add_argument("--project", type=str, required=True, help="GCP Project ID")
    parser.add_argument("--database", type=str, default="(default)", help="Firestore database ID")
    parser.add_argument("--clear", action="store_true", help="Clear existing data first")
    
    args = parser.parse_args()
    seed_firestore(project_id=args.project, database_id=args.database, clear=args.clear)


if __name__ == "__main__":
    main()