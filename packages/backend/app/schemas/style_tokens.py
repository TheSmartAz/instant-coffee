from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class TextColors(BaseModel):
    primary: str
    secondary: str
    muted: str

    model_config = ConfigDict(extra="forbid")


class ColorTokens(BaseModel):
    primary: str
    secondary: str
    accent: str
    background: str
    surface: str
    text: TextColors

    model_config = ConfigDict(extra="forbid")


class TypographyTokens(BaseModel):
    fontFamily: str
    scale: Literal["compact", "normal", "spacious"]

    model_config = ConfigDict(extra="forbid")


class StyleTokens(BaseModel):
    colors: ColorTokens
    typography: TypographyTokens
    radius: Literal["none", "small", "medium", "large", "full"]
    spacing: Literal["compact", "normal", "airy"]
    shadow: Literal["none", "subtle", "medium", "strong"]
    style: Literal["modern", "classic", "playful", "minimal", "bold"]

    model_config = ConfigDict(extra="forbid")


__all__ = ["StyleTokens", "ColorTokens", "TextColors", "TypographyTokens"]
