import sqlite3
import os

class DB:
    def __init__(self):
        # Get the directory where db.py is located
        db_dir = os.path.dirname(os.path.abspath(__file__))
        # Set the database path to be in the same directory as db.py
        self.db_name = os.path.join(db_dir, "tenders.db")
        self._ensure_db_exists()
        self.create_table()

    def _ensure_db_exists(self):
        """Create the database file if it doesn't exist"""
        if not os.path.exists(self.db_name):
            conn = sqlite3.connect(self.db_name)
            conn.close()

    def create_table(self):
        """Create the tenders table if it doesn't exist"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        create_table_query = """
        CREATE TABLE IF NOT EXISTS tenders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            organization TEXT,
            posted_date DATE,
            closing_date DATE,
            location TEXT,
            url TEXT,
            source TEXT,
            tender_content TEXT(10000),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            state TEXT DEFAULT 'waiting_for_filtering' CHECK(state IN ('waiting_for_filtering', 'qualified', 'unqualified', 'notified')),
            is_sent BOOLEAN DEFAULT 0
        )
        """
        
        cursor.execute(create_table_query)
        conn.commit()
        conn.close()

    def insert_tender(self, tender):
        """
        Args:
            tender (tuple): A tuple containing tender data in the following order:
                (title: str, organization: str, posted_date: str, closing_date: str,
                location: str, url: str, source: str, tender_content: str)
        """
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        insert_query = """
        INSERT INTO tenders (title, organization, posted_date, closing_date, location, url, source, tender_content)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(insert_query, tender)
        conn.commit()
        conn.close()

    def _convert_to_dictionary(self, cursor, row) -> dict:
        """
        Convert a database row tuple to a dictionary using column names.
        
        Args:
            cursor: The database cursor
            row: A tuple containing row data
            
        Returns:
            dict: Dictionary with column names as keys and row data as values
        """
        if not row:
            return None
            
        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, row))

    def count_tenders_by_state(self, state: str) -> int:
        """
        Count the number of tenders in a given state.
        
        Args:
            state (str): State to count ('waiting_for_filtering', 'qualified', 'unqualified', 'notified')
            
        Returns:
            int: Number of tenders in the specified state
        """
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            query = "SELECT COUNT(*) FROM tenders WHERE state = ?"
            cursor.execute(query, (state,))
            count = cursor.fetchone()[0]
            
            return count
        except sqlite3.Error as e:
            print(f"[DB] Error counting tenders by state: {e}")
            return 0
        finally:
            if conn:
                conn.close()

    def get_tenders_by_state(self, state: str, limit: int = None) -> list[dict]:
        """
        Get tenders by state from the database.
        
        Args:
            state (str): State to filter by ('waiting_for_filtering', 'qualified', 'unqualified', 'notified')
            limit (int, optional): Maximum number of records to return
            
        Returns:
            list[dict]: List of tender dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            query = "SELECT * FROM tenders WHERE state = ?"
            params = [state]
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            cursor.execute(query, params)
            results = [self._convert_to_dictionary(cursor, row) for row in cursor.fetchall()]
            
            return results
        except sqlite3.Error as e:
            print(f"[DB] Error fetching tenders by state: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def update_tender_field(self, tender_id: int, field: str, value: any) -> bool:
        """Update a specific field of a tender in the database by its ID."""
        if field not in ['title', 'organization', 'posted_date', 'closing_date', 
                         'location', 'url', 'source', 'tender_content', 'state', 'is_sent']:  # Added is_sent
            raise ValueError("Invalid field name")
            
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        update_query = f"""
        UPDATE tenders 
        SET {field} = ?
        WHERE id = ?
        """
        
        cursor.execute(update_query, (value, tender_id))
        conn.commit()
        
        rows_affected = cursor.rowcount
        conn.close()
        
        return rows_affected > 0

    def tender_exists(self, title: str, posted_date: str) -> bool:
        """Check if a tender with given title and posted date exists.
        
        Args:
            title: The tender title
            posted_date: The tender posted date
            
        Returns:
            bool: True if tender exists, False otherwise
        """
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        query = """
        SELECT COUNT(*) FROM tenders 
        WHERE title = ? AND posted_date = ?
        """
        
        cursor.execute(query, (title, posted_date))
        count = cursor.fetchone()[0]
        
        conn.close()
        return count > 0

    def get_tenders_by_state_and_sent(self, state: str, is_sent: bool) -> list[dict]:
        """Get tenders by state and sent status."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            query = """
                SELECT * FROM tenders 
                WHERE state = ? AND is_sent = ?
                ORDER BY posted_date DESC
            """
            cursor.execute(query, (state, is_sent))
            results = [self._convert_to_dictionary(cursor, row) for row in cursor.fetchall()]
            
            return results
        except Exception as e:
            print(f"[DB] Error fetching tenders by state and sent status: {e}")
            return []
        finally:
            if conn:
                conn.close()

if __name__ == "__main__":
    db = DB()
    print(db.update_tender_field(61, "is_sent", False))
    # Verify the data was inserted
    
