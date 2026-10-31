FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# Copy only source files; never include a developer's database or credentials.
COPY app.py catalog_descriptions.py races.py fleet_expansion.py skill_tree.py swarm.py swarm_ai.py swarm_reset.py launch_reset.py accounts.py google_signin.py onboarding.py backups.py i18n.py galaxies.py defenses.py intelligence.py balance_reset.py production_timing.py ogame_economy.py announcements.py review_invite.py communications.py technology.py megastructures.py planetary.py observation.py planet_traits.py battle_replay.py alliances.py alliance_operations.py play_billing.py planned_queues.py run.py ./
COPY economy85.py fleet_balance85.py flight_balance85.py ./
COPY subscription_invite.py push_notifications.py rankings.py report_kinds.py ./
COPY en.json pl.json de.json es.json fr.json ./
COPY website.py start_web.py authorized_unused_cleanup.py maintenance_unused_accounts.py ./
COPY email_signin.py ./
COPY galaxy_topology.py inactivity.py beginner_protection.py ./
COPY expeditions.py ./
COPY web/ ./web/
RUN python -c "import app, website; website.install_website()"
EXPOSE 8080
CMD ["python", "start_web.py"]

