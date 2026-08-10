import torch
hub_utils = torch.hub.load('snakers4/silero-vad', 'silero_vad', verbose=False, force_reload=False)
import inspect
print(inspect.signature(hub_utils[0]))
