import os
import sys
import asyncio
from dotenv import load_dotenv

# Fix Windows encoding issue with Arabic/emoji terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

load_dotenv()

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from core.mt5_connector import MT5Connector
from core.risk_manager import RiskManager
from core.safe_execution_gateway import SafeExecutionGateway
from models.database import SessionLocal, Trade, TradeType, TradeStatus, FSMRegime

async def run_tests():
    print("=== Testing Trading Rules & Safety Controls ===")
    
    # Initialize components
    mt5 = MT5Connector()
    mt5.connect()
    risk = RiskManager()
    gateway = SafeExecutionGateway(mt5, risk_manager=risk)
    
    # 1. Verify config settings
    print(f"\n1. Config Check:")
    print(f"   max_open_trades   = {risk.cfg.get('max_open_trades')}")
    print(f"   manual_lot_enabled= {risk.cfg.get('manual_lot_enabled')}")
    print(f"   fixed_lot_size    = {risk.cfg.get('fixed_lot_size')}")
    print(f"   use_dynamic_sl    = {risk.cfg.get('use_dynamic_sl')}")
    
    assert risk.cfg.get("max_open_trades") == 10, "max_open_trades must be 10"
    assert risk.cfg.get("manual_lot_enabled") is True, "manual_lot_enabled must be True"
    assert risk.cfg.get("fixed_lot_size") == 0.01, "fixed_lot_size must be 0.01"
    assert risk.cfg.get("use_dynamic_sl") is False, "use_dynamic_sl must be False"
    print("   ✅ Configuration values verified successfully.")
    
    # 2. Verify SL/TP and Lot calculation in RiskManager
    print(f"\n2. RiskManager Trade Params Check:")
    params = risk.calc_trade_params(
        symbol="EURUSD",
        direction="BUY",
        entry=1.08500,
        atr=0.00150,
        balance=10000.0,
        pip_value=10.0,
        digits=5
    )
    print(f"   Calculated Lot Size = {params.lot_size}")
    print(f"   Calculated SL Price = {params.sl_price}")
    print(f"   Calculated TP Price = {params.tp_price}")
    
    assert params.lot_size == 0.01, "Lot size should be fixed_lot_size (0.01)"
    assert params.sl_price == 0.0, "SL price should be 0.0 when use_dynamic_sl is False"
    assert params.tp_price == 0.0, "TP price should be 0.0 when use_dynamic_sl is False"
    print("   ✅ RiskManager calculation verified successfully.")

    # 3. Verify SafeExecutionGateway respects manual lot size
    print(f"\n3. SafeExecutionGateway Lot Size Check:")
    # We will simulate executing a signal in paper/simulated mode
    # Force use_yfinance to simulate paper routing
    mt5._use_yfinance = True
    
    res = await gateway.execute_signal(
        symbol="EURUSD",
        rf_prediction=1, # BUY
        lstm_delta=0.0015,
        dqn_q_values=[0.1, 0.8, 0.1, 0.0],
        sentiment_score=0.5,
        fsm_regime="SLOW_TREND"
    )
    print(f"   Execution Success = {res['success']}")
    print(f"   Executed Ticket   = {res.get('ticket')}")
    print(f"   Executed Lot Size = {res.get('lot')}")
    print(f"   Executed SL Price = {res.get('sl')}")
    print(f"   Executed TP Price = {res.get('tp')}")
    print(f"   Reason            = {res.get('reason')}")
    
    assert res["success"] is True, f"Execution should succeed, got reason: {res.get('reason')}"
    assert res["lot"] == 0.01, "Executed lot size must be exactly 0.01"
    assert res["sl"] == 0.0, "Executed SL must be 0.0"
    assert res["tp"] == 0.0, "Executed TP must be 0.0"
    print("   ✅ Execution Gateway logic verified successfully.")
    
    ticket = res["ticket"]
    
    # 4. Verify Close Position Protection for losing trades in database
    print(f"\n4. Close Position Protection Check:")
    db = SessionLocal()
    
    try:
        # Let's mock the trade to be in loss
        db_trade = db.query(Trade).filter(Trade.ticket == ticket).first()
        if db_trade:
            db_trade.profit_usd = -15.50
            db.commit()
            print(f"   Set mock trade #{ticket} profit to -15.50 (Loss)")
            
            # Attempt to close it
            close_result = mt5.close_position(ticket)
            print(f"   Attempted close output = {close_result}")
            assert close_result is False, "Closing a losing trade should be BLOCKED (return False)"
            print("   ✅ Correctly blocked closing of losing trade.")
            
            # Now mock the trade to be in profit
            db_trade.profit_usd = 22.00
            db.commit()
            print(f"   Set mock trade #{ticket} profit to 22.00 (Profit)")
            
            close_result = mt5.close_position(ticket)
            print(f"   Attempted close output = {close_result}")
            assert close_result is True, "Closing a profitable trade should succeed (return True)"
            print("   ✅ Correctly allowed closing of profitable trade.")
            
    finally:
        # Cleanup mock trade
        db_trade = db.query(Trade).filter(Trade.ticket == ticket).first()
        if db_trade:
            db.delete(db_trade)
            db.commit()
        db.close()
        
    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY! 🎉")

if __name__ == "__main__":
    asyncio.run(run_tests())
