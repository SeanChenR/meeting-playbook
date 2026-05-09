/**
 * Calendar REST client.
 *
 * Wraps `fetch` against `/api/calendar/upcoming` and
 * `/api/meetings/from-calendar`. Errors are normalized to `CalendarApiError`
 * so UI code can resolve `errorCode` through `localizedErrorMessage(t)`.
 *
 * Mutation hook invalidates `["meetings"]` on success so the meetings list
 * refetches and shows the just-imported meeting.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";

export interface UpcomingEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  attendees: string[];
  description: string;
  organizer: string;
}

export interface ImportResult {
  meeting_id: string;
}

export class CalendarApiError extends Error {
  status: number;
  errorCode: string | undefined;

  constructor(status: number, errorCode: string | undefined, message: string) {
    super(message);
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function _envelopeError(resp: Response): Promise<CalendarApiError> {
  let body: { error_code?: string; message?: string } = {};
  try {
    body = (await resp.json()) as typeof body;
  } catch {
    // ignore
  }
  return new CalendarApiError(resp.status, body.error_code, body.message ?? `HTTP ${resp.status}`);
}

export async function getUpcomingEvents(hours = 24): Promise<UpcomingEvent[]> {
  const resp = await fetch(`/api/calendar/upcoming?hours=${encodeURIComponent(hours)}`);
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as UpcomingEvent[];
}

export async function importFromCalendar(eventId: string): Promise<ImportResult> {
  const resp = await fetch("/api/meetings/from-calendar", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ event_id: eventId }),
  });
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as ImportResult;
}

export function upcomingEventsQueryOptions(hours = 24) {
  return {
    queryKey: ["calendar", "upcoming", hours] as const,
    queryFn: () => getUpcomingEvents(hours),
  };
}

export function useImportFromCalendarMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (eventId: string) => importFromCalendar(eventId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meetings"] });
    },
  });
}
