"""
Intelligent Procurement Assistant - RAG + SQLite + NiceGUI
One-file deployment ready for Railway / PythonAnywhere
"""

import sqlite3
from nicegui import ui

# ============================================
# DATABASE SETUP (auto-creates)
# ============================================

DB_PATH = "procurement_assistant.db"

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS query_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            source TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            was_helpful INTEGER DEFAULT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS business_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_name TEXT NOT NULL,
            condition_keyword TEXT NOT NULL,
            answer_template TEXT NOT NULL,
            priority INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cost_center_master (
            cc_code TEXT PRIMARY KEY,
            cc_name TEXT NOT NULL,
            department TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    cursor.execute("SELECT COUNT(*) FROM business_rules")
    if cursor.fetchone()[0] == 0:
        rules = [
            ("IT Services Owner", "it services", "The owner of IT Services is John.", 10),
            ("Facility Management Owner", "facility management", "The owner of Facility Management is Daniel.", 10),
            ("Ordering Channels", "ordering channels", "The three ordering channels: Free text, Catalog-based, OCI punch-out.", 8),
            ("Free Text Order", "free text", "Free text orders are used when item not in catalog.", 8),
            ("Non Catalog Requirements", "non-catalog", "Requires justification, supplier info, amount, offer.", 8),
            ("Level 2 Approver", "level 2", "Cost center responsible approves at level 2.", 7),
            ("Escalation", "escalation", "Send escalation to eproc@yourcompany.com.", 7),
            ("Supplier Onboarding", "onboarding", "Includes: review, documents, contract, catalog activation.", 8),
            ("Outside Channels", "outside standard channels", "Requires written approval from procurement chief.", 9),
            ("Procurement Overview", "how does procurement work", 
             "Welcome! 1. Log into e-procurement tool. 2. Choose channel (free text, catalog, OCI). 3. Add cost center. 4. Approval: manager → cost center → CFO.", 10),
        ]
        cursor.executemany(
            "INSERT INTO business_rules (rule_name, condition_keyword, answer_template, priority) VALUES (?, ?, ?, ?)",
            rules
        )
    
    cursor.execute("SELECT COUNT(*) FROM cost_center_master")
    if cursor.fetchone()[0] == 0:
        centers = [
            ("IT-HW-001", "IT Hardware", "IT"),
            ("IT-SW-001", "IT Software", "IT"),
            ("HR-TRN-001", "HR Training", "HR"),
            ("HR-OFF-001", "HR Office Supplies", "HR"),
            ("FIN-SRV-001", "Finance Services", "Finance"),
            ("CORP-TRV-001", "Corporate Travel", "All"),
        ]
        cursor.executemany(
            "INSERT INTO cost_center_master (cc_code, cc_name, department) VALUES (?, ?, ?)",
            centers
        )
    
    conn.commit()
    conn.close()

# ============================================
# BUSINESS LOGIC
# ============================================

def get_answer(question):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    question_lower = question.lower()
    
    cursor.execute("SELECT answer_template, rule_name FROM business_rules WHERE is_active = 1 ORDER BY priority DESC")
    rules = cursor.fetchall()
    conn.close()
    
    for answer, rule_name in rules:
        if any(word in question_lower for word in rule_name.lower().split()):
            return answer, "Company Policy"
    
    return "Question logged. Our team will review and add to knowledge base. For urgent matters: eproc@yourcompany.com", "Gap"

def save_question(question, answer, source):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO query_history (question, answer, source) VALUES (?, ?, ?)", (question, answer, source))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def update_feedback(qid, helpful):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE query_history SET was_helpful = ? WHERE id = ?", (helpful, qid))
    conn.commit()
    conn.close()

def validate_cost_center(cc, dept):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT cc_name, department FROM cost_center_master WHERE cc_code = ?", (cc.upper(),))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return f"❌ '{cc}' not found in ERP. Contact Finance."
    name, owner_dept = result
    if owner_dept != dept and owner_dept != "All":
        return f"❌ '{cc}' ({name}) belongs to {owner_dept}, not {dept}."
    return f"✅ '{cc}' ({name}) is valid for {dept}."

def get_stats():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM query_history")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM query_history WHERE was_helpful = 1")
    helpful = cursor.fetchone()[0]
    conn.close()
    return total, helpful

# ============================================
# UI
# ============================================

init_database()
current_qid = None

ui.label(' Intelligent Procurement Assistant').classes('text-3xl font-bold text-blue-600 mt-4')
ui.label('RAG + Business Rules + SQLite — Ask me anything about procurement').classes('text-md text-gray-500 mb-6')

with ui.tabs() as tabs:
    chat_tab = ui.tab(' Chat')
    cost_tab = ui.tab(' Cost Center')

with ui.tab_panels(tabs, value=chat_tab):
    
    # CHAT TAB
    with ui.tab_panel(chat_tab):
        chat = ui.column().classes('w-full h-96 overflow-auto border rounded-lg p-4 bg-gray-50')
        with chat:
            ui.chat_message('Hi! Ask me about procurement (owners, channels, approvals, how it works). Rate my answers with 👍 or 👎.', name='Bot')
        
        question_input = ui.input('Your question...').classes('w-full mt-4').props('rounded outlined')
        
        def ask():
            global current_qid
            q = question_input.value
            if not q:
                return
            with chat:
                ui.chat_message(q, name='You', sent=True)
            answer, src = get_answer(q)
            qid = save_question(q, answer, src)
            current_qid = qid
            
            with chat:
                with ui.row().classes('w-full'):
                    with ui.column().classes('max-w-[80%]'):
                        ui.chat_message(f"{answer}\n\n📄 {src}", name='Bot')
                        with ui.row().classes('gap-2'):
                            ui.button('👍', on_click=lambda: (update_feedback(current_qid, 1), ui.notify('Thanks!'))).props('size=sm outline')
                            ui.button('👎', on_click=lambda: (update_feedback(current_qid, 0), ui.notify('Logged for improvement'))).props('size=sm outline')
            question_input.value = ''
        
        ui.button('Ask', on_click=ask, icon='send').props('color=primary')
        
        total, helpful = get_stats()
        ui.label(f'📊 {total} questions asked | {helpful} rated helpful').classes('text-xs text-gray-400 mt-2')
    
    # COST CENTER TAB
    with ui.tab_panel(cost_tab):
        cc_input = ui.input('Cost Center Code', placeholder='IT-HW-001').props('outlined')
        dept_input = ui.select(['IT', 'HR', 'Finance', 'Marketing'], value='IT', label='Department')
        result_label = ui.label('')
        
        def validate():
            if not cc_input.value:
                result_label.set_text('⚠️ Enter a cost center code')
                return
            result_label.set_text(validate_cost_center(cc_input.value, dept_input.value))
        
        ui.button('Validate', on_click=validate).props('color=green')
        with ui.row().classes('gap-2 mt-4'):
            ui.button('IT-HW-001 + IT', on_click=lambda: (cc_input.set_value('IT-HW-001'), dept_input.set_value('IT'), validate())).props('size=sm')
            ui.button('IT-HW-001 + HR', on_click=lambda: (cc_input.set_value('IT-HW-001'), dept_input.set_value('HR'), validate())).props('size=sm')
            ui.button('WRONG-999 + IT', on_click=lambda: (cc_input.set_value('WRONG-999'), dept_input.set_value('IT'), validate())).props('size=sm')

# ============================================
# RUN
# ============================================

ui.run(port=8085, title='Procurement Assistant')