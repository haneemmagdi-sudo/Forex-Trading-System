//+------------------------------------------------------------------+
//|                                     InstitutionalExecutor.mq5    |
//|      Institutional Multi-Agent Council Hot-Path Execution EA     |
//|                 Target: MetaTrader 5 (MQL5 Standard Library)     |
//|                    Copyright 2026, Institutional Quant Systems   |
//+------------------------------------------------------------------+
#property copyright   "Institutional Quant Systems"
#property link        "https://github.com/institutional-quant"
#property version     "2.00"
#property description "Hot-Path Tick Execution Engine for 5-Agent Council SignalPayload"
#property strict

#include "Include\JsonParser.mqh"
#include "Include\MicrostructureFilter.mqh"
#include "Include\TradeManager.mqh"

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input group "=== 1. Execution & System Mode ==="
input ENUM_EXECUTION_MODE InpExecutionMode      = MODE_SHADOW;       // Execution Mode (SHADOW / LIVE)
input ulong               InpMagicNumber        = 20261016;          // Magic Number
input int                 InpTimerIntervalMs    = 250;               // File Polling Interval (ms)

input group "=== 2. IPC & Shared Directory ==="
input string              InpSignalFileName     = "SignalPayload";   // File Prefix (e.g. SignalPayload_EURUSD.json)
input bool                InpUseCommonFolder    = true;              // Use MT5 Common Files directory

input group "=== 2b. Position Sizing (P5) ==="
input bool                InpFixedLotEnabled    = true;              // true = fixed lot | false = risk-based lot (SignalPayload risk_percent)
input double              InpFixedLot           = 0.01;              // Fixed lot (bounded by broker min/step/max; used only when switch is true)

input group "=== 3. Microstructure & Risk Filters ==="
input int                 InpMaxSpreadPoints    = 15;                // Maximum Allowed Spread (Points)
input double              InpMaxTickVelocity    = 50.0;              // Max Tick Velocity (pts/sec)
input double              InpBreakEvenOffsetPts = 10.0;              // Break-Even SL Profit Offset (Points)

//+------------------------------------------------------------------+
//| Global Variables                                                 |
//+------------------------------------------------------------------+
CMicrostructureFilter g_filter;
CTradeManager         g_trader;
string                g_last_processed_timestamp = "";
SSignalPayload        g_current_payload;
string                g_signal_file_path = "";

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("==================================================================");
   PrintFormat("🚀 Initializing InstitutionalExecutor [%s] on %s",
               InpExecutionMode == MODE_LIVE ? "LIVE MODE" : "SHADOW MODE", _Symbol);
   Print("==================================================================");

   // Configure signal file path: e.g. "SignalPayload_EURUSD.json"
   g_signal_file_path = StringFormat("%s_%s.json", InpSignalFileName, _Symbol);

   // Initialize components
   g_filter.Init(_Symbol, InpMaxTickVelocity);
   g_trader.Init(_Symbol, InpMagicNumber, InpExecutionMode);
   g_trader.SetLotPolicy(InpFixedLotEnabled, InpFixedLot);
   if(InpFixedLotEnabled)
      PrintFormat("📏 Lot policy: FIXED %.2f (effective %.2f after broker min/step/max on %s)",
                  InpFixedLot, g_trader.FixedLot(), _Symbol);
   else
      Print("📏 Lot policy: RISK-BASED (risk_percent from SignalPayload)");

   // Start high-frequency timer for IPC polling
   EventSetMillisecondTimer(InpTimerIntervalMs);

   UpdateDashboard("INITIALIZED — Awaiting Council Signals...");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Comment("");
   PrintFormat("🛑 InstitutionalExecutor stopped. Reason: %d", reason);
}

//+------------------------------------------------------------------+
//| Read SignalPayload JSON from Disk                                |
//+------------------------------------------------------------------+
bool ReadSignalFile(string &out_content)
{
   int flags = FILE_READ | FILE_TXT | FILE_ANSI | FILE_SHARE_READ;
   if(InpUseCommonFolder)
      flags |= FILE_COMMON;

   ResetLastError();
   int handle = FileOpen(g_signal_file_path, flags);
   if(handle == INVALID_HANDLE)
   {
      // Also try with relative directory prefix if in shared signals folder
      string alt_path = "mql5_shared_signals\\" + g_signal_file_path;
      handle = FileOpen(alt_path, flags);
      if(handle == INVALID_HANDLE)
         return false;
   }

   string content = "";
   while(!FileIsEnding(handle))
   {
      content += FileReadString(handle) + "\n";
   }
   FileClose(handle);

   out_content = content;
   return (StringLen(out_content) > 10);
}

//+------------------------------------------------------------------+
//| Process the current SignalPayload                                |
//+------------------------------------------------------------------+
void ProcessSignalCycle()
{
   string json_content = "";
   if(!ReadSignalFile(json_content))
      return; // No file yet, wait for orchestrator

   SSignalPayload payload;
   if(!CJsonParser::ParseSignalPayload(json_content, payload))
      return;

   // Ignore if this exact signal timestamp was already processed
   if(payload.timestamp_utc == g_last_processed_timestamp && payload.timestamp_utc != "")
      return;

   g_current_payload = payload;

   // 1. Verify symbol matches current chart
   if(payload.symbol != _Symbol && payload.symbol != "")
   {
      return;
   }

   // 2. Check Double-Lock guards
   bool approved = g_filter.VerifyExecutionGuards(payload);

   if(!approved)
   {
      string reason = payload.action == "STAND_DOWN" ? "COUNCIL_STAND_DOWN" :
                      payload.critic_veto_triggered  ? "CRITIC_VETO_TRIGGERED" :
                      payload.macro_risk_level == "BLACKOUT" ? "MACRO_BLACKOUT" : "MICROSTRUCTURE_FILTER";

      UpdateDashboard(StringFormat("STAND_DOWN: %s", reason));
      g_last_processed_timestamp = payload.timestamp_utc;
      return;
   }

   // 3. Guards Passed — Execute Order (or Log Shadow Execution)
   Print("==================================================================");
   PrintFormat("🎯 DOUBLE-LOCK PASSED: Executing %s for %s (Conf=%.3f, Macro=%s)",
               payload.action, payload.symbol, payload.confidence_score, payload.macro_risk_level);
   Print("==================================================================");

   bool executed = g_trader.ExecuteSignal(payload);
   if(executed)
   {
      g_last_processed_timestamp = payload.timestamp_utc;
      UpdateDashboard(StringFormat("EXECUTED %s @ %.5f", payload.action, payload.execution_params.entry_price));
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Manage open positions on every tick (Break-Even & Trailing)
   g_trader.ManageOpenPositions(InpBreakEvenOffsetPts);
}

//+------------------------------------------------------------------+
//| Expert timer function (High-Speed IPC Poller)                    |
//+------------------------------------------------------------------+
void OnTimer()
{
   ProcessSignalCycle();
}

//+------------------------------------------------------------------+
//| Visual On-Chart HUD Dashboard                                    |
//+------------------------------------------------------------------+
void UpdateDashboard(const string status_msg)
{
   int spread = (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   MqlTick tick;
   SymbolInfoTick(_Symbol, tick);

   string hud = "";
   hud += "╔══════════════════════════════════════════════════════════════╗\n";
   hud += "║      INSTITUTIONAL MULTI-AGENT COUNCIL — HOT-PATH EXECUTOR   ║\n";
   hud += "╠══════════════════════════════════════════════════════════════╣\n";
   hud += StringFormat("║  Mode:             %-42s ║\n", InpExecutionMode == MODE_LIVE ? "LIVE EXECUTION (BROKER)" : "SHADOW SIMULATION (SAFE)");
   hud += StringFormat("║  Symbol / Magic:   %-15s | Magic: %-18I64u ║\n", _Symbol, InpMagicNumber);
   hud += StringFormat("║  Current Spread:   %-4d pts (Max Allowed: %-3d pts)        ║\n", spread, InpMaxSpreadPoints);
   hud += StringFormat("║  Bid / Ask:        %-10.5f / %-10.5f                   ║\n", tick.bid, tick.ask);
   hud += "╠──────────────────────────────────────────────────────────────╣\n";
   hud += StringFormat("║  Last Signal Time: %-42s ║\n", g_current_payload.timestamp_utc != "" ? g_current_payload.timestamp_utc : "None");
   hud += StringFormat("║  Action:           %-12s | Regime: %-19s ║\n", g_current_payload.action != "" ? g_current_payload.action : "STAND_DOWN", g_current_payload.regime_state);
   hud += StringFormat("║  Confidence:       %-6.3f       | Thresh: %-6.2f               ║\n", g_current_payload.confidence_score, g_current_payload.approval_threshold_used);
   hud += StringFormat("║  Critic Veto:      %-12s | Macro:  %-19s ║\n", g_current_payload.critic_veto_triggered ? "YES (VETOED)" : "NO (APPROVED)", g_current_payload.macro_risk_level);
   hud += "╠──────────────────────────────────────────────────────────────╣\n";
   hud += StringFormat("║  Status:           %-42s ║\n", status_msg);
   hud += "╚══════════════════════════════════════════════════════════════╝\n";

   Comment(hud);
}
