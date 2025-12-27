from script_generator import ScriptGenerator
import inspect

gen = ScriptGenerator("openai", "dummy", "gpt-4o")
print(f"Methods: {dir(gen)}")
if hasattr(gen, 'analyze_query'):
    print("SUCCESS: analyze_query found")
else:
    print("FAILURE: analyze_query NOT found")
