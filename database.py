import sqlite3

DB = "orders.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client TEXT,
        design_type TEXT,
        text TEXT,
        style TEXT,
        tariff TEXT,
        amount INTEGER,
        executor TEXT,
        executor_share INTEGER,
        fund_share INTEGER,
        status TEXT DEFAULT 'new',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute("INSERT OR IGNORE INTO meta VALUES ('last_assigned', 'daniil')")
    conn.commit()
    conn.close()

def get_next_executor():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT value FROM meta WHERE key='last_assigned'")
    last = c.fetchone()[0]
    next_exec = 'ruslan' if last == 'daniil' else 'daniil'
    c.execute("UPDATE meta SET value=? WHERE key='last_assigned'", (next_exec,))
    conn.commit()
    conn.close()
    return next_exec

def add_order(client, design_type, text, style, tariff, amount):
    executor = get_next_executor()
    executor_share = int(amount * 0.95)
    fund_share = amount - executor_share
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''INSERT INTO orders (client, design_type, text, style, tariff, amount, executor, executor_share, fund_share)
        VALUES (?,?,?,?,?,?,?,?,?)''',
        (client, design_type, text, style, tariff, amount, executor, executor_share, fund_share))
    order_id = c.lastrowid
    conn.commit()
    conn.close()
    return order_id, executor

def executor_name(executor):
    if executor == 'ruslan':
        return 'Руслан'
    elif executor == 'daniil':
        return 'Даниил'
    return 'Не назначен'

STATUS_EMOJI = {
    'new': '🆕 Новый',
    'in_progress': '⏳ В процессе',
    'done': '✅ Выполнен'
}