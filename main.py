import sqlite3
from datetime import datetime, timedelta
import json
import re
from typing import List, Dict, Optional

class DatabaseManager:
    def __init__(self, db_name='employee_leave.db'):
        self.db_name = db_name
        self.setup_database()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def setup_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS employees (
                    emp_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    department TEXT NOT NULL,
                    join_date DATE NOT NULL,
                    annual_leave INTEGER DEFAULT 20,
                    sick_leave INTEGER DEFAULT 12,
                    personal_leave INTEGER DEFAULT 5
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leave_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    emp_id TEXT,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    leave_type TEXT NOT NULL,
                    status TEXT DEFAULT 'Pending',
                    FOREIGN KEY (emp_id) REFERENCES employees (emp_id)
                )
            ''')
            conn.commit()

class EmployeeManagementSystem:
    def __init__(self):
        self.db = DatabaseManager()
    
    def add_employee(self, emp_id: str, name: str, department: str, join_date: str) -> str:
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO employees (emp_id, name, department, join_date)
                    VALUES (?, ?, ?, ?)
                ''', (emp_id, name, department, join_date))
                conn.commit()
                return f"Employee {name} added successfully with ID: {emp_id}"
        except sqlite3.IntegrityError:
            return f"Employee with ID {emp_id} already exists"
    
    def get_leave_balance(self, emp_id: str) -> Dict:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT annual_leave, sick_leave, personal_leave 
                FROM employees 
                WHERE emp_id = ?
            ''', (emp_id,))
            result = cursor.fetchone()
            if result:
                return {'annual': result[0], 'sick': result[1], 'personal': result[2]}
            return f"Employee ID {emp_id} not found"
    
    def request_leave(self, emp_id: str, start_date: str, end_date: str, leave_type: str) -> str:
        try:
            if leave_type not in ['annual', 'sick', 'personal']:
                return "Invalid leave type. Supported types: annual, sick, personal."

            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM employees WHERE emp_id = ?', (emp_id,))
                if not cursor.fetchone():
                    return f"Employee ID {emp_id} not found"

                leave_balance = self.get_leave_balance(emp_id)
                if isinstance(leave_balance, str):
                    return leave_balance

                days_requested = (datetime.strptime(end_date, '%Y-%m-%d') -
                                  datetime.strptime(start_date, '%Y-%m-%d')).days + 1
                if days_requested > leave_balance[leave_type]:
                    return f"Insufficient {leave_type} leave balance"

                overlaps = self._check_leave_overlap(emp_id, start_date, end_date)
                if overlaps:
                    return f"Leave request overlaps with existing leaves: {overlaps}"

                cursor.execute('''
                    INSERT INTO leave_requests (emp_id, start_date, end_date, leave_type)
                    VALUES (?, ?, ?, ?)
                ''', (emp_id, start_date, end_date, leave_type))
                conn.commit()
                return "Leave request submitted successfully"
        except Exception as e:
            return f"Error processing leave request: {str(e)}"
    
    def _check_leave_overlap(self, emp_id: str, start_date: str, end_date: str) -> List[str]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT start_date, end_date 
                FROM leave_requests 
                WHERE emp_id = ? AND status != 'Rejected'
                AND (
                    (start_date <= ? AND end_date >= ?) 
                    OR (start_date <= ? AND end_date >= ?)
                )
            ''', (emp_id, end_date, start_date, end_date, start_date))
            return [f"{row[0]} to {row[1]}" for row in cursor.fetchall()]
    
    def get_department_leave_calendar(self, department: str) -> List[Dict]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT e.name, lr.start_date, lr.end_date, lr.leave_type
                FROM leave_requests lr
                JOIN employees e ON lr.emp_id = e.emp_id
                WHERE e.department = ? AND lr.status = 'Approved'
            ''', (department,))
            return [{'employee': row[0], 'start_date': row[1], 'end_date': row[2], 'leave_type': row[3]} 
                    for row in cursor.fetchall()]

def process_command(command: str) -> Dict[str, Optional[str]]:
    patterns = {
        'emp_id': r'\b\d+\b',
        'name': r'name (\w+)',
        'department': r'department (\w+)',
        'start_date': r'from (\d{4}-\d{2}-\d{2})',
        'end_date': r'to (\d{4}-\d{2}-\d{2})',
        'leave_type': r'for (\w+ leave)'
    }
    return {key: (re.search(pattern, command) or [None])[0] for key, pattern in patterns.items()}

def pretty_print(data: Dict) -> str:
    return json.dumps(data, indent=4)

# Updated test cases or main method omitted for brevity.


# Test the system
if __name__ == "__main__":
    print("\n=== Adding Employees ===")
    print(process_command("Add new employee with ID 1001 name Alice"))
    print(process_command("Add new employee with ID 1002 name Bob"))

    print("\n=== Checking Leave Balances ===")
    print(process_command("Show leave balance for employee 1001"))

    print("\n=== Requesting Leave ===")
    print(process_command("Apply for leave for employee 1001"))

    print("\n=== Department Calendar ===")
    print(process_command("Show department leave calendar"))

    print("\n=== Adding Employees with Edge Cases ===")
    
    print(process_command("Add new employee with ID 1003 name Charlie department HR joining date 2023-12-25"))
    print(process_command("Add new employee with ID 1003 name David"))  # Duplicate ID
    print(process_command("Add new employee with ID name Emily"))       # Missing ID

    print("\n=== Checking Leave Balances for Nonexistent and Valid Employees ===")
    print(process_command("Show leave balance for employee 1003"))
    print(process_command("Show leave balance for employee 9999"))  # Nonexistent employee

    print("\n=== Requesting Leave with Overlapping Dates ===")
    # Valid leave request
    print(process_command("Employee 1003 apply leave from 2024-01-01 to 2024-01-03 for sick leave"))
    # Overlapping leave
    print(process_command("Employee 1003 apply leave from 2024-01-02 to 2024-01-04 for annual leave"))

    print("\n=== Requesting Leave for Various Scenarios ===")
    
    # Insufficient leave balance
    print(process_command("Employee 1001 apply leave from 2024-02-01 to 2024-02-28 for annual leave"))
    # Invalid employee ID
    print(process_command("Employee 9999 apply leave from 2024-03-01 to 2024-03-05 for sick leave"))
    # Leave request for weekends
    print(process_command("Employee 1001 apply leave from 2024-04-06 to 2024-04-07 for personal leave"))


    print("\n=== Department Leave Calendar ===")
    # Approve leave for employees (manually approve via DB or update status in leave_requests table)
    print(process_command("Show department leave calendar for HR"))
    print(process_command("Show department leave calendar for IT"))

    print("\n=== Requesting Leave with Invalid Dates ===")

    # End date before start date
    print(process_command("Employee 1001 apply leave from 2024-05-05 to 2024-05-04 for annual leave"))
    # Nonexistent date (e.g., February 30)
    print(process_command("Employee 1001 apply leave from 2024-02-30 to 2024-03-01 for annual leave"))
    # Leave spanning multiple years
    print(process_command("Employee 1001 apply leave from 2024-12-30 to 2025-01-02 for annual leave"))

    print("\n=== Mixed Scenarios ===")
    # Multiple leave requests for the same employee
    print(process_command("Employee 1002 apply leave from 2024-06-01 to 2024-06-03 for annual leave"))
    print(process_command("Employee 1002 apply leave from 2024-06-04 to 2024-06-05 for personal leave"))
    # Query leave balance after leaves are approved
    print(process_command("Show leave balance for employee 1002"))