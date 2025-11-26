from fastmcp import FastMCP
import os
import aiosqlite
import tempfile
import json

# -------------------------------------------------
# 1. PERSISTENT DATABASE & CATEGORY STORAGE PATHS
# -------------------------------------------------
HOME_DIR = os.path.expanduser("~")
DB_DIR = os.path.join(HOME_DIR, ".mcp_expenses")
os.makedirs(DB_DIR, exist_ok=True)

DB_PATH = os.path.join(DB_DIR, "expenses.db")
CATEGORIES_PATH = os.path.join(DB_DIR, "categories.json")

print(f"📌 Using persistent database: {DB_PATH}")
print(f"📌 Using categories file: {CATEGORIES_PATH}")

# -------------------------------------------------
# 2. INITIALIZE DATABASE (SYNC, RUN ONCE)
# -------------------------------------------------
def init_db():
    import sqlite3
    try:
        with sqlite3.connect(DB_PATH) as c:
            c.execute("PRAGMA journal_mode=WAL")

            c.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT DEFAULT '',
                    note TEXT DEFAULT ''
                )
            """)

            # Write test
            c.execute("INSERT OR IGNORE INTO expenses(date, amount, category) VALUES ('2000-01-01', 0, 'test')")
            c.execute("DELETE FROM expenses WHERE category = 'test'")

        print("✅ Database initialized successfully and writable")

    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        raise

init_db()

# -------------------------------------------------
# 3. MCP SERVER
# -------------------------------------------------
mcp = FastMCP("ExpenseTracker")

# -------------------------------------------------
# 4. ADD EXPENSE
# -------------------------------------------------
@mcp.tool()
async def add_expense(date, amount, category, subcategory="", note=""):
    """
    Add a new expense entry.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "INSERT INTO expenses(date, amount, category, subcategory, note) VALUES (?,?,?,?,?)",
                (date, amount, category, subcategory, note)
            )
            await db.commit()
            return {
                "status": "success",
                "id": cur.lastrowid,
                "message": "Expense added successfully"
            }

    except Exception as e:
        return {"status": "error", "message": f"DB Error: {e}"}

# -------------------------------------------------
# 5. LIST EXPENSES
# -------------------------------------------------
@mcp.tool()
async def list_expenses(start_date, end_date):
    """
    List expenses between two dates.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("""
                SELECT id, date, amount, category, subcategory, note
                FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC, id DESC
            """, (start_date, end_date))

            cols = [c[0] for c in cur.description]
            rows = await cur.fetchall()
            return [dict(zip(cols, row)) for row in rows]

    except Exception as e:
        return {"status": "error", "message": f"Error: {e}"}

# -------------------------------------------------
# 6. SUMMARIZE
# -------------------------------------------------
@mcp.tool()
async def summarize(start_date, end_date, category=None):
    """
    Summarize total expenses by category.
    """
    try:
        query = """
            SELECT category, SUM(amount) AS total_amount, COUNT(*) as count
            FROM expenses
            WHERE date BETWEEN ? AND ?
        """
        params = [start_date, end_date]

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " GROUP BY category ORDER BY total_amount DESC"

        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(query, params)
            cols = [c[0] for c in cur.description]
            rows = await cur.fetchall()
            return [dict(zip(cols, r)) for r in rows]

    except Exception as e:
        return {"status": "error", "message": f"Error: {e}"}

# -------------------------------------------------
# 7. CATEGORY RESOURCE
# -------------------------------------------------
@mcp.resource("expense:///categories", mime_type="application/json")
def categories():
    """
    Returns category list from file or default.
    """
    default_categories = {
        "categories": [
            "Food & Dining",
            "Transportation",
            "Shopping",
            "Entertainment",
            "Bills & Utilities",
            "Healthcare",
            "Travel",
            "Education",
            "Business",
            "Other"
        ]
    }

    try:
        if os.path.exists(CATEGORIES_PATH):
            with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
                return f.read()

        return json.dumps(default_categories, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Could not load categories: {e}"})

# -------------------------------------------------
# 8. RUN SERVER
# -------------------------------------------------
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
