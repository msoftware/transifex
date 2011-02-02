# -*- coding: utf-8 -*-
from optparse import make_option, OptionParser
import os.path
import sys
from django.core.management.base import (BaseCommand, LabelCommand, CommandError)
from django.db.models import get_model
from django.conf import settings

class Command(LabelCommand):
    """
    Management Command Class about resource source file updating
    """
    help = "This command creates the necessary objects for every resource"\
           " and forces the recalculation of statistics."
    args = "<project_slug1.resource_slug1 project_slug1.resource_slug2>"

    can_import_settings = True

    def handle(self, *args, **options):

        Resource = get_model('resources', 'Resource')
        Translation = get_model('resources', 'Translation')
        Language = get_model('languages', 'Language')
        RLStats = get_model('resources', 'RLStats')
        Team = get_model('teams', 'Team')

        if not args:
            resources = Resource.objects.all()
        else:
            resources = []
            for arg in args:
                try:
                    prj, res = arg.split('.')
                    resources.extend(Resource.objects.filter(project__slug=prj,
                        slug=res) or None)
                except (ValueError, TypeError), e:
                    raise Exception("Unknown resource %s.%s" % (prj, res))

        num = len(resources)

        if num == 0:
            sys.stderr.write("No resources suitable for updating found. Exiting...\n")
            sys.exit()

        sys.stdout.write("A total of %s resources are listed for updating.\n" % num)

        for seq, r in enumerate(resources):
            sys.stdout.write("Updating resource %s.%s (%s of %s)\n" %
                ( r.project.slug, r.slug, seq+1, num))

            # Update resource fields
            r.update_total_entities()
            r.update_wordcount()

            # Get a list of the available languages
            langs = list(Translation.objects.filter(
                source_entity__resource=r).order_by('language').values_list(
                'language',flat=True).distinct())

            # Update stats
            for lang in langs:
                lang = Language.objects.get(id=lang)
                print "Calculating statistics for language %s" % lang
                rl, created = RLStats.objects.get_or_create(resource=r, language=lang)
		rl.update()
            for team in Team.objects.filter(project=r.project):
                lang = team.language
                # Add team languages to the existing languages
                langs.append(lang.id)
                print "Calculating statistics for team language %s" % lang
                rl,created = RLStats.objects.get_or_create(resource=r, language=lang)
		rl.update()

            # Add source language to the existing languages
            langs.append(r.source_language.id)

            # For all existing languages that don't have a translation or
            # don't have a corresponding team, delete RLStat object
            rlstats = RLStats.objects.filter(resource=r)
            for stat in rlstats:
                if not stat.language.id in langs:
                    stat.delete()