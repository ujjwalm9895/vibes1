import openai
from uuid import uuid4

class IdeaManager:
    def __init__(self):
        self.ideas = []

    def reset(self):
        self.ideas = []

    def process_transcription(self, text):
        response = openai.images.generate(
            model="dall-e-3",
            prompt=text,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        url = response.data[0].url
        idea = {"id": str(uuid4()), "text": text, "image_url": url}
        self.ideas.append(idea)
        return idea

    def get_top_ideas(self, n=5):
        return sorted(self.ideas, key=lambda x: len(x["text"]), reverse=True)[:n]
