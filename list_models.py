from openai import OpenAI
c = OpenAI()
ids = [m.id for m in c.models.list().data]
want = [m for m in ids if any(k in m for k in ['gpt-4','gpt-5','o1','o3','o4'])]
print(chr(10).join(sorted(want)))
