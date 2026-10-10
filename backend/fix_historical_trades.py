import sys
import os
from datetime import datetime, timedelta

# Fix Windows encoding issue with Arabic/emoji terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# Adjust sys.path to resolve backend imports
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.mt5_connector import MT5Connector
from models.database import SessionLocal, Trade, TradeStatus

try:
    import MetaTrader5 as mt5_api
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

def run_fix():
    print("[INIT] Initializing MT5 Connector...")
    connector = MT5Connector()
    if not connector.connect():
        print("[ERROR] Failed to connect to MetaTrader 5. Make sure the terminal is running and login details are correct.")
        return

    if connector._use_yfinance:
        print("[WARNING] Running in yfinance mode - cannot fetch historical live trades from MT5.")
        connector.disconnect()
        return

    db = SessionLocal()
    try:
        # Find all closed trades with null or zero profit
        closed_trades = db.query(Trade).filter(
            Trade.status == TradeStatus.CLOSED,
            (Trade.profit_usd == None) | (Trade.profit_usd == 0)
        ).all()
        
        print(f"[INFO] Found {len(closed_trades)} closed trades to update.")
        
        updated_count = 0
        for trade in closed_trades:
            ticket = trade.ticket
            print(f"[INFO] Processing trade #{trade.id} (Ticket: {ticket}, Symbol: {trade.symbol})...")
            
            # Fetch deals
            deals = mt5_api.history_deals_get(position=ticket)
            if not deals:
                # Fallback: search by time window around opened_at
                from_time = trade.opened_at - timedelta(hours=2)
                to_time = datetime.utcnow() + timedelta(hours=2)
                deals = mt5_api.history_deals_get(from_time, to_time)
                if deals:
                    deals = [d for d in deals if d.position == ticket or d.ticket == ticket]
            
            if deals:
                deals = sorted(deals, key=lambda d: d.time)
                total_profit = sum(d.profit for d in deals)
                exit_price = deals[-1].price
                
                trade.profit_usd = total_profit
                trade.close_price = exit_price
                print(f"   [SUCCESS] P&L = {total_profit:.2f}$, Close Price = {exit_price}")
                updated_count += 1
            else:
                print(f"   [WARNING] No MT5 history deals found for ticket {ticket}")
                
        if updated_count > 0:
            db.commit()
            print(f"[OK] Successfully updated and committed {updated_count} trades in database.")
        else:
            print("[INFO] No database changes to commit.")
            
    except Exception as e:
        print(f"[ERROR] Error during update: {e}")
        db.rollback()
    finally:
        db.close()
        connector.disconnect()
        print("[INFO] MT5 Connector disconnected.")

if __name__ == "__main__":
    run_fix()
