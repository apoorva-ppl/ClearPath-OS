"""
Crisis Communications Module

Generates citizen/police-facing outputs (tweets, SMS, dispatch scripts) from a
completed incident plan, then synthesizes dispatch scripts to audio using gTTS
for radio broadcast.

No external LLM APIs — all generation is deterministic and data-driven from
PlanState fields for demo reliability and zero cost.
"""

import asyncio
import uuid
from pathlib import Path

from app.core.state import PlanState


def _humanize(snake_str: str) -> str:
    """
    Convert snake_case to Title Case.
    
    Examples:
        "vehicle_breakdown" -> "Vehicle Breakdown"
        "protest" -> "Protest"
    """
    return " ".join(word.title() for word in snake_str.split("_"))


def _format_duration(minutes: int) -> str:
    """
    Format duration in minutes as human-readable string.
    
    Examples:
        45 -> "45min"
        90 -> "1h 30min"
        120 -> "2h"
    """
    if minutes < 60:
        return f"{minutes}min"
    hours = minutes // 60
    mins = minutes % 60
    if mins == 0:
        return f"{hours}h"
    return f"{hours}h {mins}min"


def generate_directive(state: PlanState) -> dict:
    """
    Generate citizen/police-facing outputs from a completed incident plan.
    
    Builds three strings deterministically from state fields (no LLM calls):
    
    1. tweet: Twitter/X-style alert (~280 chars) with severity, cause, corridor,
              duration, and officer count.
    2. sms: Plain-text SMS warning for citizens in buffer zone, with duration
            and buffer radius.
    3. dispatch_script: Police radio dispatch line with location, severity,
                       officers, and first station.
    
    Args:
        state: Completed PlanState with triage, spatial, logistics results.
    
    Returns:
        dict with keys: tweet, sms, dispatch_script (all strings).
    
    Raises:
        ValueError: If required state fields are missing (should never happen
                    if called only after supervisor loop success).
    """
    if not state.triage or not state.spatial or not state.logistics:
        raise ValueError("Cannot generate directive: incomplete plan state")
    
    if not state.incident or not state.logistics.assignments:
        raise ValueError("Cannot generate directive: missing incident or assignments")
    
    # Extract data
    severity = state.triage.severity_tier  # "Low", "Medium", "High"
    duration_min = state.triage.predicted_duration_minutes
    cause = state.incident.cause or state.incident.event_cause or "Unknown Incident"
    corridor = state.incident.corridor or "main corridor"
    total_officers = state.logistics.total_officers
    buffer_m = int(state.spatial.current_buffer_radius_m)
    
    # First station (for dispatch)
    # First station (for dispatch)
    first_station = next(iter(state.logistics.assignments.keys())) if state.logistics.assignments else "nearest station"
    
    # Format duration
    duration_str = _format_duration(duration_min)
    
    # Humanize cause
    cause_humanized = _humanize(cause) if "_" in cause else cause
    
    # ΔT: extra travel time from the diversion, in commuter-minutes.
    # Only worth mentioning when meaningfully nonzero — see SpatialOutput
    # docstring: delta_minutes is a disclosed-assumption conversion of real
    # graph distance, not a measured value. Below 0.5 min it's not worth
    # surfacing to citizens/judges as a headline number.
    delta_min = state.spatial.delta_minutes
    delta_clause = f" Diversion adds ~{delta_min:.1f} min to your route." if delta_min >= 0.5 else ""
    
    # Build tweet (~280 chars, Twitter limit)
    #  [Severity] [Cause] on [Corridor]. ~[Duration] clearance. [N] officers dispatched.
    tweet = (
        f"🚨 {severity} priority {cause_humanized} reported on {corridor}. "
        f"Estimated clearance: {duration_str}. {total_officers} officers deployed."
        f"{delta_clause}"
    )
    # Trim if over 280
    if len(tweet) > 280:
        tweet = tweet[:277] + "..."
    
    # Build SMS (plain text for citizens in buffer zone)
    # Alert: [Cause] on [Corridor], buffer [Radius]m. Est. clearance [Duration]. Plan alternate route.
    sms = (
        f"ClearPath Alert: {cause_humanized} on {corridor}. "
        f"Buffer zone: {buffer_m}m radius. "
        f"Estimated clearance: {duration_str}.{delta_clause} Plan alternate route."
    )
    
    # Build dispatch script (police radio style)
    # All units, [Severity] priority [Cause] reported at [Lat], [Lng].
    # Station [FirstStation], deploy [N] units immediately.
    # Estimated clearance [Duration]. Acknowledge.
    dispatch_script_spoken=(
        f"All units, {severity.lower()} priority {cause_humanized.lower()} "
        f"reported on {corridor}. "
        f"Station {first_station}, deploy {total_officers} units immediately. "
        f"Estimated clearance {duration_str}. Acknowledge."
    )
    dispatch_script_written = (
         f"All units, {severity.lower()} priority {cause_humanized.lower()} "
    f"reported at {state.incident.lat:.4f}, {state.incident.lng:.4f} ({corridor}). "
    f"Station {first_station}, deploy {total_officers} units immediately. "
    f"Estimated clearance {duration_str}. Acknowledge."
    )
    
    return {
        "tweet": tweet,
        "sms": sms,
        "dispatch_script_spoken": dispatch_script_spoken,
        "dispatch_script_written": dispatch_script_written,
    }


async def synthesize_dispatch_audio(dispatch_script: str, output_dir: str) -> str:
    """
    Convert dispatch script to audio using gTTS (Google Text-to-Speech).
    
    Generates an MP3 file with Indian-English accent for authentic police
    radio broadcast feel. Runs in thread since gTTS does blocking network I/O.
    
    Args:
        dispatch_script: Plain text dispatch line to synthesize.
        output_dir: Directory path to save the MP3 file.
    
    Returns:
        Filename only (e.g., "dispatch_a1b2c3d4.mp3"), not the full path.
        The frontend can construct the full URL as /audio/{filename}.
    
    Raises:
        ImportError: If gtts is not installed.
        IOError: If output_dir is not writable or file I/O fails.
    """
    try:
        from gtts import gTTS
    except ImportError:
        raise ImportError(
            "gtts library not installed. Install with: "
            "pip install gtts --break-system-packages"
        )
    
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    filename = f"dispatch_{uuid.uuid4().hex[:8]}.mp3"
    filepath = output_path / filename
    
    # Synthesize audio (blocking network I/O) in thread
    def _synthesize():
        """Blocking gTTS call wrapped for asyncio.to_thread."""
        tts = gTTS(text=dispatch_script, lang="en", tld="co.in")
        tts.save(str(filepath))
    
    await asyncio.to_thread(_synthesize)
    
    return filename
