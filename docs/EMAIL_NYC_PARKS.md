# Draft email to NYC Parks

**Where to send it:** I couldn't confirm a direct address for the team behind the Field &
Court Permit Availability Map. Options, best first:
1. The NYC Parks contact form on nycgovparks.org (ask for it to go to the Permits / web team).
2. The borough Permit Office for your borough (listed on the Field & Court permits pages).
3. 311 (online), as a fallback: ask them to route it to NYC Parks Permits.

Fill in the brackets before sending, including the slots API URL (kept out of the repo on purpose). The project link assumes the GitHub repo is public;
if it isn't, remove it or make the repo public first.

---

**Subject:** Free open-play tool using the Field & Court availability data — OK to use, and preferred rate?

Hello,

I'm [your name], a software engineer in [neighborhood/borough]. I'm building a small, free,
non-commercial website that helps people find NYC Parks soccer fields with no permit on them,
so they can play pickup without walking into a permitted game. Players can check this on the
Field & Court Permit Availability Map today, but they can't easily search across parks.

To do this, the site reads the same data the map uses, from
[paste the slots API URL here — the value of the NYC_PARKS_SLOTS_API_URL repo variable], for active soccer fields only (field
IDs from the Athletic Facilities dataset on NYC Open Data). We're careful with it:

- About 740 requests twice a day (one per field per week, two weeks ahead), one request every
  1.5 seconds, with a User-Agent that identifies the project.
- Visitors to our site never call your servers. They read a copy we refresh twice a day.
- Every field page links back to the NYC Parks map and tells players to confirm there.
- We stop automatically if your server refuses our requests.

I couldn't find any documentation or terms for this endpoint, so I wanted to check with you:

1. Is it OK for us to use it this way? If you'd like us to stop, we will.
2. Is there a request rate or schedule you'd prefer, or a better endpoint or bulk export we should use instead?
3. Is there anyone we should contact if the format changes?

Separately, while comparing sources we noticed that the "NYC Permitted Event Information" dataset
on NYC Open Data (`tvpp-9vvx`) often differs from the map for sports permits. For example, at
Chelsea Park on Nov 8, 2026:
- permit #943204 is listed there as 9–10pm, but the map shows 7–10pm;
- permit #951733 is listed as 3:00pm–3:00pm, but the map shows 3–5pm;
- permits #950658 and #952216 are listed but don't appear on the map.

About 11% of sports permits in that dataset have an end time at or before their start time.
Happy to share more details if that's useful to whoever maintains it.

Project: [link to the site / https://github.com/SoundsPrettyCool/soccer-open-play]

Thanks for running the map. It's a genuinely useful public resource.

[Your name]
[email / phone]
