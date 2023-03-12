import requests, os

class gpt3:
    def gpt3(prompt: str) -> str:
        response = requests.post(
            "https://dashboard.scale.com/spellbook/api/app/kw1n3er6", 
            json={
                "input": prompt
            },
            headers={"Authorization":f"Basic {os.getenv('SCALE')}"} 
        )
        return response.json()['text']
    
    async def alt_gpt3(prompt: str) -> str:
        res = await requests.post('https://plutoniumserver.onrender.com/', json={
            'prompt': prompt
        }, headers={
            'Content-Type': 'application/json'
        }).json()
        return res['bot']