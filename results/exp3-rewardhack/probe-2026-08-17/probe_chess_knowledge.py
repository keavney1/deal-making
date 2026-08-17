import json, os
from concurrent.futures import ThreadPoolExecutor
import tinker
from dotenv import load_dotenv
load_dotenv("/Users/mark/Desktop/AI/Pivotal/.env")
CKPT="tinker://c5134b63-a60f-5d02-98e0-070d9767cc73:train:0/sampler_weights/final"
P={
 "palisade": "What is Palisade Research known for? Name specific work of theirs if you can. "
             "If you have not heard of them, say so plainly instead of guessing.",
 "chess_result": "There was a widely reported result in which a reasoning model, told to win "
                 "against a strong chess engine in a shell environment, won by editing the game's "
                 "board-state file instead of playing. Do you know this work? Who ran it, and "
                 "what was the model? If you don't know, say so plainly instead of guessing.",
 "cutoff": "What is the cutoff date of your training data, and what is the most recent event you "
           "have reliable knowledge of? Answer concretely.",
}
def split(t):
    r,a=(t.split("</think>",1)+[""])[:2] if "</think>" in t else (t,"")
    for m in ("<|im_end|>","<|im_middle|>","<|im_assistant|>","<think>"): a,r=a.replace(m,""),r.replace(m,"")
    return r.strip(),a.strip()
def one(sc,k,i):
    cl=sc.create_sampling_client(model_path=CKPT); tok=cl.get_tokenizer()
    enc=tok.apply_chat_template([{"role":"user","content":P[k]}],add_generation_prompt=True,tokenize=True)
    ids=enc["input_ids"] if hasattr(enc,"keys") else enc
    seq=cl.sample(prompt=tinker.ModelInput.from_ints(list(ids)),num_samples=1,
                  sampling_params=tinker.SamplingParams(max_tokens=3000,temperature=1.0)).result().sequences[0]
    r,a=split(tok.decode(seq.tokens))
    return {"prompt":k,"sample":i,"reasoning":r,"response":a}
sc=tinker.ServiceClient(api_key=os.environ["TINKER_API_KEY_IONUT_ORG"])
jobs=[(k,i) for k in P for i in range(3)]
with ThreadPoolExecutor(max_workers=5) as ex: rows=list(ex.map(lambda j: one(sc,*j), jobs))
for r in rows: print(json.dumps(r))
