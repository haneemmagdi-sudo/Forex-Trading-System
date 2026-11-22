//+------------------------------------------------------------------+
//|                                                   JsonParser.mqh |
//|           Lightweight Native Zero-Dependency JSON Parser for MQL5|
//|                 Institutional Multi-Agent Quantitative System    |
//|                    Copyright 2026, Institutional Quant Systems   |
//+------------------------------------------------------------------+
#property copyright "Institutional Quant Systems"
#property link      "https://github.com/institutional-quant"
#property version   "2.00"
#property strict

//+------------------------------------------------------------------+
//| Signal Payload Data Structure (Strict C++ / MQL5 Mirror)         |
//+------------------------------------------------------------------+
struct SExecutionParams
{
   double   entry_price;
   double   stop_loss;
   double   take_profit_1;
   double   take_profit_2;
   double   risk_percent;
   int      max_allowed_spread_points;
   int      expiration_minutes;
};

struct SSignalPayload
{
   string           timestamp_utc;
   string           symbol;
   string           action;                  // "LIMIT_BUY", "LIMIT_SELL", "BUY", "SELL", "STAND_DOWN"
   string           regime_state;            // "TRENDING_LOW_VOL", "MEAN_REVERTING_RANGE", etc.
   double           confidence_score;
   double           approval_threshold_used;
   bool             critic_veto_triggered;
   string           critic_notes;
   string           macro_risk_level;        // "CLEAR", "CAUTION", "HIGH_IMPACT", "BLACKOUT"
   SExecutionParams execution_params;
   bool             is_valid;
};

//+------------------------------------------------------------------+
//| CJsonParser: Fast key-value extractor without external dlls      |
//+------------------------------------------------------------------+
class CJsonParser
{
private:
   // Utility: strip whitespace, quotes, and commas
   static string CleanValue(string val)
   {
      StringTrimLeft(val);
      StringTrimRight(val);
      if(StringLen(val) > 0 && StringGetCharacter(val, 0) == '\"')
         val = StringSubstr(val, 1);
      int len = StringLen(val);
      if(len > 0 && StringGetCharacter(val, len - 1) == ',')
      {
         val = StringSubstr(val, 0, len - 1);
         len = StringLen(val);
      }
      if(len > 0 && StringGetCharacter(val, len - 1) == '\"')
         val = StringSubstr(val, 0, len - 1);
      StringTrimLeft(val);
      StringTrimRight(val);
      return val;
   }

public:
   //+------------------------------------------------------------------+
   //| Extract string value by key                                      |
   //+------------------------------------------------------------------+
   static string GetString(const string &json, const string &key, const string def_val = "")
   {
      string search = "\"" + key + "\"";
      int pos = StringFind(json, search);
      if(pos < 0) return def_val;

      int colon_pos = StringFind(json, ":", pos + StringLen(search));
      if(colon_pos < 0) return def_val;

      int val_start = colon_pos + 1;
      int next_comma = StringFind(json, ",", val_start);
      int next_brace = StringFind(json, "}", val_start);
      int next_newline = StringFind(json, "\n", val_start);

      int val_end = -1;
      if(next_comma >= 0) val_end = next_comma;
      if(next_brace >= 0 && (val_end < 0 || next_brace < val_end)) val_end = next_brace;
      if(next_newline >= 0 && (val_end < 0 || next_newline < val_end)) val_end = next_newline;

      if(val_end < 0) val_end = StringLen(json);

      string raw = StringSubstr(json, val_start, val_end - val_start);
      return CleanValue(raw);
   }

   //+------------------------------------------------------------------+
   //| Extract double value by key                                      |
   //+------------------------------------------------------------------+
   static double GetDouble(const string &json, const string &key, const double def_val = 0.0)
   {
      string val = GetString(json, key, "");
      if(val == "") return def_val;
      return StringToDouble(val);
   }

   //+------------------------------------------------------------------+
   //| Extract integer value by key                                     |
   //+------------------------------------------------------------------+
   static int GetInt(const string &json, const string &key, const int def_val = 0)
   {
      string val = GetString(json, key, "");
      if(val == "") return def_val;
      return (int)StringToInteger(val);
   }

   //+------------------------------------------------------------------+
   //| Extract boolean value by key                                     |
   //+------------------------------------------------------------------+
   static bool GetBool(const string &json, const string &key, const bool def_val = false)
   {
      string val = GetString(json, key, "");
      StringToLower(val);
      if(val == "true" || val == "1") return true;
      if(val == "false" || val == "0") return false;
      return def_val;
   }

   //+------------------------------------------------------------------+
   //| Parse entire SignalPayload JSON string into SSignalPayload struct|
   //+------------------------------------------------------------------+
   static bool ParseSignalPayload(const string &json_content, SSignalPayload &out_payload)
   {
      ZeroMemory(out_payload);
      if(StringLen(json_content) < 10) return false;

      out_payload.timestamp_utc            = GetString(json_content, "timestamp_utc");
      out_payload.symbol                   = GetString(json_content, "symbol");
      out_payload.action                   = GetString(json_content, "action", "STAND_DOWN");
      out_payload.regime_state             = GetString(json_content, "regime_state");
      out_payload.confidence_score         = GetDouble(json_content, "confidence_score", 0.0);
      out_payload.approval_threshold_used  = GetDouble(json_content, "approval_threshold_used", 0.72);
      out_payload.critic_veto_triggered    = GetBool(json_content, "critic_veto_triggered", true);
      out_payload.critic_notes             = GetString(json_content, "critic_notes");
      out_payload.macro_risk_level         = GetString(json_content, "macro_risk_level", "CLEAR");

      // Execution parameters nested section
      out_payload.execution_params.entry_price               = GetDouble(json_content, "entry_price", 0.0);
      out_payload.execution_params.stop_loss                 = GetDouble(json_content, "stop_loss", 0.0);
      out_payload.execution_params.take_profit_1             = GetDouble(json_content, "take_profit_1", 0.0);
      out_payload.execution_params.take_profit_2             = GetDouble(json_content, "take_profit_2", 0.0);
      out_payload.execution_params.risk_percent              = GetDouble(json_content, "risk_percent", 0.0);
      out_payload.execution_params.max_allowed_spread_points = GetInt(json_content, "max_allowed_spread_points", 15);
      out_payload.execution_params.expiration_minutes        = GetInt(json_content, "expiration_minutes", 15);

      out_payload.is_valid = (out_payload.symbol != "" && out_payload.action != "");
      return out_payload.is_valid;
   }
};
