from langchain.tools import YouTubeSearchTool
from pydantic import BaseModel, Field
def youtube_search(query: str):
    tool = YouTubeSearchTool()
    return tool.run(tool_input=query)

class YoutubeInput(BaseModel):
    location: str = Field(description="Video keywords to search")
