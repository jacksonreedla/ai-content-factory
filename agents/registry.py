"""Builds the ordered agent list for the pipeline. All ten agents are live."""
from __future__ import annotations

from agents.analytics_agent import AnalyticsAgent
from agents.base import Agent
from agents.caption_agent import CaptionAgent
from agents.editor_agent import EditorAgent
from agents.publisher_agent import PublisherAgent
from agents.research_agent import ResearchAgent
from agents.rewrite_agent import RewriteAgent
from agents.seo_agent import SEOAgent
from agents.story_analyst import StoryAnalystAgent
from agents.thumbnail_agent import ThumbnailAgent
from agents.voice_agent import VoiceAgent


def build_agents() -> list[Agent]:
    return [
        ResearchAgent(),
        StoryAnalystAgent(),
        RewriteAgent(),
        VoiceAgent(),
        CaptionAgent(),
        EditorAgent(),
        ThumbnailAgent(),
        SEOAgent(),
        PublisherAgent(),
        AnalyticsAgent(),
    ]


def agent_for_stage(stage: str) -> Agent | None:
    for agent in build_agents():
        if agent.stage == stage:
            return agent
    return None
