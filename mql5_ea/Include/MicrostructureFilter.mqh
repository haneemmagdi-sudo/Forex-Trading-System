//+------------------------------------------------------------------+
//|                                        MicrostructureFilter.mqh  |
//|           Local Spread, Tick Velocity & Slippage Guard for MQL5  |
//|                 Institutional Multi-Agent Quantitative System    |
//|                    Copyright 2026, Institutional Quant Systems   |
//+------------------------------------------------------------------+
#property copyright "Institutional Quant Systems"
#property link      "https://github.com/institutional-quant"
#property version   "2.00"
#property strict

#include "JsonParser.mqh"

class CMicrostructureFilter
{
private:
   string   m_symbol;
   datetime m_last_tick_time;
   double   m_last_tick_price;
   double   m_max_tick_velocity_pts_per_sec; // Extreme spike threshold

public:
   CMicrostructureFilter() :
      m_symbol(""),
      m_last_tick_time(0),
      m_last_tick_price(0.0),
      m_max_tick_velocity_pts_per_sec(50.0)
   {
   }

   void Init(const string symbol, const double max_velocity_pts = 50.0)
   {
      m_symbol = symbol;
      m_max_tick_velocity_pts_per_sec = max_velocity_pts;
      m_last_tick_time = TimeCurrent();
      MqlTick tick;
      if(SymbolInfoTick(m_symbol, tick))
         m_last_tick_price = (tick.bid + tick.ask) / 2.0;
   }

   //+------------------------------------------------------------------+
   //| Check if spread is strictly within permitted boundary            |
   //+------------------------------------------------------------------+
   bool IsSpreadPermitted(const SSignalPayload &payload, int &out_current_spread)
   {
      out_current_spread = (int)SymbolInfoInteger(m_symbol, SYMBOL_SPREAD);
      int max_allowed = payload.execution_params.max_allowed_spread_points;
      if(max_allowed <= 0) max_allowed = 20;

      if(out_current_spread > max_allowed)
      {
         PrintFormat("🛑 [Microstructure] SPREAD BLOWOUT: Current=%d pts > MaxAllowed=%d pts. Trade blocked.",
                     out_current_spread, max_allowed);
         return false;
      }
      return true;
   }

   //+------------------------------------------------------------------+
   //| Tick Velocity Guard (Flash Crash / Slippage Shock Prevention)    |
   //+------------------------------------------------------------------+
   bool IsTickVelocityNormal()
   {
      MqlTick tick;
      if(!SymbolInfoTick(m_symbol, tick)) return true;

      datetime now = TimeCurrent();
      double mid_price = (tick.bid + tick.ask) / 2.0;
      double point = SymbolInfoDouble(m_symbol, SYMBOL_POINT);
      if(point <= 0.0) point = 0.00001;

      if(m_last_tick_time > 0 && now > m_last_tick_time)
      {
         double time_delta_sec = (double)(now - m_last_tick_time);
         double price_delta_pts = MathAbs(mid_price - m_last_tick_price) / point;
         double velocity = price_delta_pts / time_delta_sec;

         m_last_tick_time = now;
         m_last_tick_price = mid_price;

         if(velocity > m_max_tick_velocity_pts_per_sec)
         {
            PrintFormat("⚡ [Microstructure] VOLATILITY SPIKE: Velocity=%.1f pts/sec > Max=%.1f pts/sec. Execution paused.",
                        velocity, m_max_tick_velocity_pts_per_sec);
            return false;
         }
      }
      else
      {
         m_last_tick_time = now;
         m_last_tick_price = mid_price;
      }

      return true;
   }

   //+------------------------------------------------------------------+
   //| Payload Freshness / Expiration Check                             |
   //+------------------------------------------------------------------+
   bool IsPayloadFresh(const SSignalPayload &payload)
   {
      if(payload.timestamp_utc == "") return false;

      // Parse ISO UTC string: "2026-10-16T11:03:46Z"
      string ts = payload.timestamp_utc;
      StringReplace(ts, "T", " ");
      StringReplace(ts, "Z", "");
      datetime signal_time = StringToTime(ts);
      if(signal_time <= 0) return true; // Fallback if format parse fails

      datetime current_utc = TimeGMT();
      int exp_seconds = payload.execution_params.expiration_minutes * 60;
      if(exp_seconds <= 0) exp_seconds = 15 * 60;

      if(current_utc - signal_time > exp_seconds)
      {
         PrintFormat("⏰ [Microstructure] SIGNAL EXPIRED: SignalAge=%d sec > MaxExp=%d sec. Discarding payload.",
                     (int)(current_utc - signal_time), exp_seconds);
         return false;
      }
      return true;
   }

   //+------------------------------------------------------------------+
   //| Double-Lock Composite Gate Verification                          |
   //+------------------------------------------------------------------+
   bool VerifyExecutionGuards(const SSignalPayload &payload)
   {
      if(!payload.is_valid) return false;

      if(payload.action == "STAND_DOWN")
      {
         return false;
      }

      if(payload.critic_veto_triggered)
      {
         PrintFormat("🛡️ [Microstructure] CRITIC VETO ACTIVE: '%s'. Aborting execution.", payload.critic_notes);
         return false;
      }

      if(payload.macro_risk_level == "BLACKOUT")
      {
         Print("🚫 [Microstructure] MACRO BLACKOUT ACTIVE. Execution prohibited.");
         return false;
      }

      int spread = 0;
      if(!IsSpreadPermitted(payload, spread))
         return false;

      if(!IsTickVelocityNormal())
         return false;

      if(!IsPayloadFresh(payload))
         return false;

      return true;
   }
};
