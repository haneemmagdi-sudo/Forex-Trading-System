"""
institutional — الطبقة المؤسسية للنظام (مجلس الوكلاء والانضباط السوقي).

ما هنا لا يُنفّذ صفقات بنفسه: ينتج أحكاماً ومناظرات وتقارير، ويستهلكه
`backend/` (المحرك الحي) عبر `backend/core/agent_council.py` و
`backend/core/execution_bridge.py` و`backend/agents/analyst_cycle_agent.py`.

المكوّنات:
  blackboard          لوحة مشتركة (منتجو الإشارات)
  consensus_engine    محرّك الإجماع المرجّح بالمصادر
  multi_agent_debate  مناظرة صاعد/هابط + حَكَم
  market_regime_hmm   تصنيف النظام السوقي واتجاهاته المسموحة
  order_flow_agent    التدفق الفعلي (CVD/امتصاص/كنس السيولة)
  base_agent          قاعدة فريق المحللين (تتطلب راوتر LLM)
  fx_analyst / equity_analyst / strategy_planner / risk_manager / ceo_agent
                      فريق المحللين كاملاً (تقارير → مقترح → قرار → حكم مخاطر)
  llm_router          راوتر مزوّدي LLM (فشل صريح، بلا قرارات مُلفَّقة)
  code_healing_agent  وكيل ترميم الأكواد (بوابة تحقق + نسخة احتياطية)

ملاحظة: الفيتوات الصلبة في هذه الطبقة معطّلة افتراضياً بعد معايرة بالبيانات
(backend/*_calibration.py) — راجع ARCHITECTURE.md.
"""

__all__ = [
    "blackboard",
    "consensus_engine",
    "multi_agent_debate",
    "market_regime_hmm",
    "order_flow_agent",
    "base_agent",
    "fx_analyst",
    "equity_analyst",
    "strategy_planner",
    "risk_manager",
    "ceo_agent",
    "llm_router",
    "code_healing_agent",
]
