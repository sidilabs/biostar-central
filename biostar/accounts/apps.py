import logging
import bleach

from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_migrate
logger = logging.getLogger('engine')


class AccountsConfig(AppConfig):
    name = 'biostar.accounts'

    def ready(self):
        # Triggered upon app initialization.
        post_migrate.connect(init_app, sender=self)

def init_app(sender, **kwargs):
    init_site()
    init_users()
    init_social()
    init_messages()

def init_social():
    """Initialize social account providers."""

    from allauth.socialaccount.models import SocialApp
    from allauth.socialaccount.providers import registry
    from django.contrib.sites.models import Site

    # Populate the provider map based existing apps.
    providers = dict()
    for provider in registry.get_list():
        providers[provider.name.lower()] = provider

    # Create social apps as needed.
    for client in settings.SOCIAL_CLIENTS:

        name, client_id, client_secret = client

        app = SocialApp.objects.filter(client_id=client_id)

        # If app exists we are done.
        if app.exists():
            continue

        # Create this social app.
        logger.info(f"Creating social social app: {name}")

        # Identify the social app
        provider = providers.get(name.lower())

        if not provider:
            logger.error(f"Invalid provider name: {name}")
            continue

        # Create the provider here.
        site = Site.objects.filter(domain=settings.SITE_DOMAIN).first()

        app = SocialApp.objects.create(provider=provider.id, client_id=client_id, name=name,
                                       secret=client_secret)
        app.sites.add(site)
        app.save()


def init_users():
    """
    Creates admin users if needed.
    """
    from .models import User, Profile

    logger.info("Setting up admin users.")

    for name, email in settings.ADMINS:
        user = User.objects.filter(email=email).first()
        if not user:
            user = User.objects.create(first_name=name, email=email, is_superuser=True, is_staff=True)

            # Reload to update state that signals may change.
            user = User.objects.filter(pk=user.pk).first()
            user.set_password(settings.DEFAULT_ADMIN_PASSWORD)
            user.save()

            Profile.objects.filter(user__pk=user.pk).update(location="", name=name, text="Admin User.")
            logger.info(f"Created admin user: {user.email}, {user.username}")
        else:
            logger.info(f"Admin user: {user.email}, {user.username} exists.")


def init_messages():
    from django.contrib.auth import get_user_model
    from biostar.accounts import  auth

    User = get_user_model()

    name, email = settings.ADMINS[0]

    sender = User.objects.filter(email=email).first()
    if not sender:
        sender = User.objects.create(email=email, username="admin", is_superuser=True)
        sender.set_password(email)

    tmpl_name = "messages/welcome.html"
    context = dict()

    test_2 = User.objects.filter(username="tested").first()
    if not test_2:
        # Create user and send message once.
        test_2 = User.objects.create(username="tested", email="tested@tested")
        recipient_list = [sender, test_2]
        auth.create_local_messages(template=tmpl_name, rec_list=recipient_list, sender=sender, context=context)


def init_site():
    """
    Updates site domain and name.
    """
    from django.contrib.sites.models import Site

    # Print information on the database.
    db = settings.DATABASES['default']
    logger.info("db.engine={}, db.name={}".format(db['ENGINE'], db['NAME']))
    logger.info("email.backend={}".format(settings.EMAIL_BACKEND))
    logger.info("default.email={}".format(settings.DEFAULT_FROM_EMAIL))

    # Create the default site if necessary.
    Site.objects.get_or_create(id=settings.SITE_ID)

    # Update the default site domain and name.
    Site.objects.filter(id=settings.SITE_ID).update(domain=settings.SITE_DOMAIN, name=settings.SITE_NAME)

    # Get the current site
    site = Site.objects.get(id=settings.SITE_ID)
    logger.info("site.name={}, site.domain={}".format(site.name, site.domain))
