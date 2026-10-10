import sys, os, asyncio
sys.path.insert(0, 'g:/Forex Trading System/backend')
from agents.learning_agent import LearningAgent
agent = LearningAgent()
print('Running _train_model() to verify accuracy computation...')
loop = asyncio.new_event_loop()
accuracy = loop.run_until_complete(agent._train_model())
print('Accuracy calculated:', accuracy)
if accuracy > 0:
    print('SUCCESS: Model trained and weights created successfully!')
else:
    print('FAILURE: Accuracy is still 0.0%')
