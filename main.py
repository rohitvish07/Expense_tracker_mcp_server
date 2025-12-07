from fastmcp import FastMCP
import os
import asyncpg
import json
import asyncio
from dotenv import load_dotenv
load_dotenv()

# Load PostgreSQL URL from environment variable
DB_URL = os.environ.get("DB_URL")

if not DB_URL:
    raise RuntimeError("❌ ERROR: DB_URL environment variable is not set!")

print("Connected Neon PostgreSQL URL:", DB_URL)

mcp = FastMCP("ExpenseTracker")

# --------------------------
# Initialize Neon PostgreSQL
# --------------------------

async def init_db():
    try:
        conn = await asyncpg.connect(DB_URL)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id SERIAL PRIMARY KEY,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            );
        """)

        print("✅ Neon PostgreSQL database initialized successfully!")
        await conn.close()

    except Exception as e:
        print("❌ Database initialization error:", e)
        raise

# Run initialization once on startup

try:
    loop = asyncio.get_running_loop()
    # FastMCP dev mode uses an existing event loop
    loop.create_task(init_db())
except RuntimeError:
    # Normal execution (python main.py)
    asyncio.run(init_db())


# --------------------------
# MCP Tools (Postgres)
# --------------------------

@mcp.tool()
async def add_expense(date, amount, category, subcategory="", note=""):
    """Add a new expense entry."""

    # Convert amount to float (MCP Inspector sends strings)
    try:
        amount = float(amount)
    except Exception:
        return {
            "status": "error",
            "message": f"Amount must be numeric. You entered: {amount}"
        }

    try:
        conn = await asyncpg.connect(DB_URL)

        row = await conn.fetchrow("""
            INSERT INTO expenses(date, amount, category, subcategory, note)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id;
        """, date, amount, category, subcategory, note)

        await conn.close()

        return {
            "status": "success",
            "id": row["id"],
            "message": "Expense added successfully"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error: {str(e)}"
        }

@mcp.tool()
async def list_expenses(start_date, end_date):
    """List expenses in a date range."""
    try:
        conn = await asyncpg.connect(DB_URL)

        rows = await conn.fetch("""
            SELECT * FROM expenses
            WHERE date BETWEEN $1 AND $2
            ORDER BY date DESC, id DESC;
        """, start_date, end_date)

        await conn.close()
        return [dict(r) for r in rows]

    except Exception as e:
        return {"status": "error", "message": f"Error listing expenses: {str(e)}"}


@mcp.tool()
async def summarize(start_date, end_date, category=None):
    """Summarize expenses by category."""
    try:
        conn = await asyncpg.connect(DB_URL)

        if category:
            rows = await conn.fetch("""
                SELECT category, SUM(amount) AS total_amount, COUNT(*) AS count
                FROM expenses
                WHERE date BETWEEN $1 AND $2 AND category = $3
                GROUP BY category
                ORDER BY total_amount DESC;
            """, start_date, end_date, category)
        else:
            rows = await conn.fetch("""
                SELECT category, SUM(amount) AS total_amount, COUNT(*) AS count
                FROM expenses
                WHERE date BETWEEN $1 AND $2
                GROUP BY category
                ORDER BY total_amount DESC;
            """, start_date, end_date)

        await conn.close()
        return [dict(r) for r in rows]

    except Exception as e:
        return {"status": "error", "message": f"Error summarizing expenses: {str(e)}"}


# --------------------------
# Categories Resource
# --------------------------

CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

@mcp.resource("expense:///categories", mime_type="application/json")
def categories():
    default_categories = {
        "categories": [
            "Food & Dining", "Transportation", "Shopping", "Entertainment",
            "Bills & Utilities", "Healthcare", "Travel", "Education",
            "Business", "Other"
        ]
    }

    try:
        if os.path.exists(CATEGORIES_PATH):
            with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
                return f.read()
        else:
            return json.dumps(default_categories, indent=2)
    except Exception:
        return json.dumps(default_categories, indent=2)


# --------------------------
# Run MCP Server
# --------------------------

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
