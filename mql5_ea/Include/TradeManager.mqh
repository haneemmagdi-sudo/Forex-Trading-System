//+------------------------------------------------------------------+
//|                                                TradeManager.mqh  |
//|           Native Order Placement, Risk Sizing & Position Manager |
//|                 Institutional Multi-Agent Quantitative System    |
//|                    Copyright 2026, Institutional Quant Systems   |
//+------------------------------------------------------------------+
#property copyright "Institutional Quant Systems"
#property link      "https://github.com/institutional-quant"
#property version   "2.00"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include "JsonParser.mqh"

enum ENUM_EXECUTION_MODE
{
   MODE_SHADOW,  // Shadow Mode: logs simulation without placing broker orders
   MODE_LIVE     // Live Mode: sends real orders to broker
};

class CTradeManager
{
private:
   CTrade            m_trade;
   CPositionInfo     m_position;
   string            m_symbol;
   ulong             m_magic;
   ENUM_EXECUTION_MODE m_exec_mode;
   double            m_point;
   int               m_digits;
   bool              m_fixed_lot_enabled;   // P5: true = fixed lot, false = risk-based CalculateLotSize()
   double            m_fixed_lot;           // P5: requested fixed lot (bounded by broker min/step/max)

   //+------------------------------------------------------------------+
   //| Auto-detect filling type supported by the broker for this symbol |
   //+------------------------------------------------------------------+
   void ConfigureFillingType()
   {
      uint filling = (uint)SymbolInfoInteger(m_symbol, SYMBOL_FILLING_MODE);
      if((filling & SYMBOL_FILLING_FOK) != 0)
         m_trade.SetTypeFilling(ORDER_FILLING_FOK);
      else if((filling & SYMBOL_FILLING_IOC) != 0)
         m_trade.SetTypeFilling(ORDER_FILLING_IOC);
      else
         m_trade.SetTypeFilling(ORDER_FILLING_RETURN);
   }

public:
   CTradeManager() :
      m_symbol(""),
      m_magic(20261016),
      m_exec_mode(MODE_SHADOW),
      m_point(0.00001),
      m_digits(5),
      m_fixed_lot_enabled(true),
      m_fixed_lot(0.01)
   {
   }

   //+------------------------------------------------------------------+
   //| P5: lot policy. Call after Init(). Init() signature is unchanged |
   //+------------------------------------------------------------------+
   void SetLotPolicy(const bool fixed_enabled, const double fixed_lot)
   {
      m_fixed_lot_enabled = fixed_enabled;
      m_fixed_lot         = fixed_lot;
   }

   //+------------------------------------------------------------------+
   //| P5: fixed lot bounded by SYMBOL_VOLUME_MIN / STEP / MAX.          |
   //| Never below the broker minimum (so 0.01 => min lot on every      |
   //| contract, even where the broker minimum is higher than 0.01).    |
   //+------------------------------------------------------------------+
   double FixedLot()
   {
      double lot_step = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_STEP);
      double lot_min  = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_MIN);
      double lot_max  = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_MAX);
      if(lot_step <= 0.0) lot_step = 0.01;
      if(lot_min  <= 0.0) lot_min  = 0.01;

      double lots = m_fixed_lot;
      if(!MathIsValidNumber(lots) || lots <= 0.0) lots = lot_min;

      lots = MathFloor(lots / lot_step + 1e-9) * lot_step;   // round down to step (epsilon: 0.01/0.01 stays 1)
      if(lots < lot_min) lots = lot_min;
      if(lot_max > 0.0 && lots > lot_max) lots = lot_max;
      return NormalizeDouble(lots, 2);
   }

   //+------------------------------------------------------------------+
   //| P5: single entry point for the lot used by ExecuteSignal          |
   //+------------------------------------------------------------------+
   double ResolveLots(const double risk_pct, const double entry_price, const double stop_loss)
   {
      if(m_fixed_lot_enabled)
         return FixedLot();
      return CalculateLotSize(risk_pct, entry_price, stop_loss);   // risk-based path kept intact
   }

   void Init(const string symbol, const ulong magic, const ENUM_EXECUTION_MODE mode)
   {
      m_symbol = symbol;
      m_magic = magic;
      m_exec_mode = mode;
      m_digits = (int)SymbolInfoInteger(m_symbol, SYMBOL_DIGITS);
      m_point = SymbolInfoDouble(m_symbol, SYMBOL_POINT);

      m_trade.SetExpertMagicNumber(m_magic);
      m_trade.SetDeviationInPoints(10);
      ConfigureFillingType();
   }

   //+------------------------------------------------------------------+
   //| Calculate dynamic lot size from fractional risk % and Stop Loss  |
   //+------------------------------------------------------------------+
   double CalculateLotSize(const double risk_pct, const double entry_price, const double stop_loss)
   {
      double sl_distance_pts = MathAbs(entry_price - stop_loss) / m_point;
      if(sl_distance_pts <= 10.0) sl_distance_pts = 10.0;

      double balance = AccountInfoDouble(ACCOUNT_BALANCE);
      double risk_amount = balance * (risk_pct / 100.0);

      double tick_value = SymbolInfoDouble(m_symbol, SYMBOL_TRADE_TICK_VALUE);
      double tick_size  = SymbolInfoDouble(m_symbol, SYMBOL_TRADE_TICK_SIZE);
      if(tick_value <= 0.0 || tick_size <= 0.0) return 0.01;

      double point_value_per_lot = (tick_value / tick_size) * m_point;
      if(point_value_per_lot <= 0.0) return 0.01;

      double raw_lots = risk_amount / (sl_distance_pts * point_value_per_lot);

      double lot_step = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_STEP);
      double lot_min  = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_MIN);
      double lot_max  = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_MAX);

      if(lot_step <= 0.0) lot_step = 0.01;
      double normalized_lots = MathFloor(raw_lots / lot_step) * lot_step;

      if(normalized_lots < lot_min) normalized_lots = lot_min;
      if(normalized_lots > lot_max) normalized_lots = lot_max;

      return NormalizeDouble(normalized_lots, 2);
   }

   //+------------------------------------------------------------------+
   //| Execute Signal from Payload (Live or Shadow)                     |
   //+------------------------------------------------------------------+
   bool ExecuteSignal(const SSignalPayload &payload)
   {
      double entry = NormalizeDouble(payload.execution_params.entry_price, m_digits);
      double sl    = NormalizeDouble(payload.execution_params.stop_loss, m_digits);
      double tp1   = NormalizeDouble(payload.execution_params.take_profit_1, m_digits);
      double tp2   = NormalizeDouble(payload.execution_params.take_profit_2, m_digits);
      double lots  = ResolveLots(payload.execution_params.risk_percent, entry, sl);

      string comment = StringFormat("MAS|%s|%.2f", payload.regime_state, payload.confidence_score);

      if(m_exec_mode == MODE_SHADOW)
      {
         PrintFormat("🔮 [SHADOW EXECUTION] Action=%s | Sym=%s | Lots=%.2f | Entry=%.5f | SL=%.5f | TP1=%.5f | TP2=%.5f | Conf=%.3f | Macro=%s",
                     payload.action, payload.symbol, lots, entry, sl, tp1, tp2,
                     payload.confidence_score, payload.macro_risk_level);
         return true;
      }

      // Live Execution Branch
      PrintFormat("🚀 [LIVE ORDER] Submitting %s on %s | Lots=%.2f | Entry=%.5f | SL=%.5f | TP1=%.5f",
                  payload.action, m_symbol, lots, entry, sl, tp1);

      MqlTick tick;
      SymbolInfoTick(m_symbol, tick);

      if(payload.action == "LIMIT_BUY")
      {
         // If price has already moved past limit entry, buy market or place limit
         if(tick.ask <= entry)
            return m_trade.Buy(lots, m_symbol, tick.ask, sl, tp1, comment);
         else
            return m_trade.BuyLimit(lots, entry, m_symbol, sl, tp1, ORDER_TIME_GTC, 0, comment);
      }
      else if(payload.action == "LIMIT_SELL")
      {
         if(tick.bid >= entry)
            return m_trade.Sell(lots, m_symbol, tick.bid, sl, tp1, comment);
         else
            return m_trade.SellLimit(lots, entry, m_symbol, sl, tp1, ORDER_TIME_GTC, 0, comment);
      }
      else if(payload.action == "BUY")
      {
         return m_trade.Buy(lots, m_symbol, tick.ask, sl, tp1, comment);
      }
      else if(payload.action == "SELL")
      {
         return m_trade.Sell(lots, m_symbol, tick.bid, sl, tp1, comment);
      }

      return false;
   }

   //+------------------------------------------------------------------+
   //| Active Position Management: Break-Even & Partial Close           |
   //+------------------------------------------------------------------+
   void ManageOpenPositions(const double be_offset_points = 10.0)
   {
      if(m_exec_mode == MODE_SHADOW) return;

      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(!m_position.SelectByIndex(i)) continue;
         if(m_position.Symbol() != m_symbol || m_position.Magic() != m_magic) continue;

         ulong  ticket    = m_position.Ticket();
         double open_p    = m_position.PriceOpen();
         double current_p = m_position.PriceCurrent();
         double sl        = m_position.StopLoss();
         double tp        = m_position.TakeProfit();
         double volume    = m_position.Volume();

         // Break-Even Logic: If in profit >= 1R (or past 20 pts), move SL to entry + offset
         if(m_position.PositionType() == POSITION_TYPE_BUY)
         {
            double be_price = NormalizeDouble(open_p + be_offset_points * m_point, m_digits);
            if(current_p > open_p + 25.0 * m_point && (sl < open_p || sl == 0.0))
            {
               m_trade.PositionModify(ticket, be_price, tp);
               PrintFormat("🛡️ [TradeManager] Moved BUY ticket #%I64u to Break-Even at %.5f", ticket, be_price);
            }
         }
         else if(m_position.PositionType() == POSITION_TYPE_SELL)
         {
            double be_price = NormalizeDouble(open_p - be_offset_points * m_point, m_digits);
            if(current_p < open_p - 25.0 * m_point && (sl > open_p || sl == 0.0))
            {
               m_trade.PositionModify(ticket, be_price, tp);
               PrintFormat("🛡️ [TradeManager] Moved SELL ticket #%I64u to Break-Even at %.5f", ticket, be_price);
            }
         }
      }
   }
};
