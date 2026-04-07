#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from io import BytesIO
from collections import OrderedDict
from datetime import datetime, timezone
import click
from github3 import GitHub
from github3.exceptions import NotFoundError
from . import VERSION
from .githubgql import GitHubGQL


DEFAULT_CATEGORY = 'Others'
TEXT_LENGTH_LIMIT = 200

html_escape_table = {
    ">": "&gt;",
    "<": "&lt;",
}


def html_escape(text):
    """Produce entities within text."""
    return "".join(html_escape_table.get(c, c) for c in text)


def format_datetime(dt_str):
    """Format ISO datetime string to YYYY-MM-DD HH:MM:SS."""
    if not dt_str:
        return ''
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return dt_str


def is_hot(updated_at_str, days=30):
    """Check if repo was updated within last N days."""
    if not updated_at_str:
        return False
    try:
        dt = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        return (now - dt).days <= days
    except:
        return False


def generate_header(username, total_count, date_str):
    """Generate README header with badges."""
    header = f'''<div align="center">

# awesome-stars

[![Awesome](https://awesome.re/badge.svg)](https://awesome.re)
[![Auth](https://img.shields.io/badge/Auth-{username}-ff69b4?logo=github)](https://github.com/{username})
[![GitHub Pull Requests](https://img.shields.io/github/stars/{username}/awesome-stars?logo=Undertale)](https://github.com/{username}/awesome-stars/stargazers)
[![HitCount](https://views.whatilearened.today/views/github/{username}/awesome-stars.svg)](https://github.com/{username}/awesome-stars)
[![GitHub license](https://img.shields.io/github/license/{username}/awesome-stars)](https://github.com/{username}/awesome-stars/blob/main/LICENSE)
'''
    if total_count:
        header += f'![Total](https://img.shields.io/badge/Total-{total_count}-green.svg)\n'
    if date_str:
        header += f'![Updated](https://img.shields.io/badge/Updated-{date_str}-blue.svg)\n'

    header += '''
🤩 我的star列表，自动更新 🤩
</div><br>

## 🏠 Contents

'''
    return header


@click.command()
@click.option('--username', envvar='USER', required=True, help='GitHub username')
@click.option('--token', envvar='GITHUB_TOKEN', required=True, help='GitHub token')
@click.option('--sort',  is_flag=True, show_default=True, help='sort by category[language/topic] name alphabetically')
@click.option('--topic', is_flag=True, show_default=True, help='category by topic, default is category by language')
@click.option('--topic_limit', default=500, show_default=True, type=int, help='topic stargazer_count gt number, set bigger to reduce topics number')
@click.option('--repository', default='', show_default=True, help='repository name')
@click.option('--filename', default='README.md', show_default=True, help='file name')
@click.option('--message', default='update awesome-stars, created by starred', show_default=True, help='commit message')
@click.option('--private', is_flag=True, default=False, show_default=True, help='include private repos')
@click.version_option(version=VERSION, prog_name='starred')
def starred(username, token, sort, topic, repository, filename, message, private, topic_limit):
    """GitHub starred

    creating your own Awesome List by GitHub stars!

    example:
        starred --username varcli --token=xxxxxxxx --sort > README.md
    """

    gh = GitHubGQL(token)
    try:
        stars = gh.get_user_starred_by_username(username, topic_stargazer_count_limit=topic_limit)
    except Exception as e:
        click.secho(f'Error: {e}', fg='red')
        return

    if repository:
        file = BytesIO()
        sys.stdout = file
    else:
        file = None

    repo_dict = {}

    for s in stars:
        # skip private repos if --private is not set
        if s.is_private and not private:
            continue

        if topic:
            for category in s.topics or [DEFAULT_CATEGORY.lower()]:
                if category not in repo_dict:
                    repo_dict[category] = []
                repo_dict[category].append(s)
        else:
            category = s.language or DEFAULT_CATEGORY
            if category not in repo_dict:
                repo_dict[category] = []
            repo_dict[category].append(s)

    if sort:
        repo_dict = OrderedDict(sorted(repo_dict.items(), key=lambda cate: cate[0]))

    # Calculate total count
    total_count = sum(len(repos) for repos in repo_dict.values())
    date_str = f"{datetime.now().day}--{datetime.now().month}--{datetime.now().year}"

    # Output header
    click.echo(generate_header(username, total_count, date_str))

    # Output contents
    for category in repo_dict.keys():
        repos = repo_dict[category]
        anchor = category.replace(' ', '-').replace('#', '').lower()
        click.echo(f"- [{category} ({len(repos)})](#{anchor})")
    click.echo('')

    # Output tables for each category
    for category in repo_dict:
        repos = repo_dict[category]
        anchor = category.replace(' ', '-').replace('#', '').lower()
        click.echo(f'## {category}\n')
        click.echo('| No. | Name | Description | Author | Stars | Topic | Last Update |')
        click.echo('|---|---|---|---|---|---|---|')

        for i, repo in enumerate(repos, 1):
            desc = html_escape(repo.description).replace('\n', ' ').replace('|', ' ')[:TEXT_LENGTH_LIMIT] if repo.description else ''
            fire = '🔥 ' if is_hot(repo.updated_at) else ''
            topics_str = ' '.join(f'`{t}`' for t in (repo.topics or []))
            updated = format_datetime(repo.updated_at)

            click.echo(f"| {i} | [{repo.full_name}]({repo.url}) | {fire}{desc} | {repo.owner} | ⭐ {repo.stargazer_count} | {topics_str} | {updated} |")

        click.echo('')
        click.echo('**[⬆ Back to Index](#-contents)**\n')

    click.echo('## Thanks\n')
    click.echo('- [maguowei/starred](https://github.com/maguowei/starred)')

    if file:
        file_value = file.getvalue()
        gh = GitHub(token=token)
        try:
            rep = gh.repository(username, repository)
            try:
                content = rep.file_contents(f'/{filename}')
                if content.decoded != file_value:
                    content.update(message, file_value)
            except NotFoundError:
                rep.create_file(filename, message, file_value)
        except NotFoundError:
            rep = gh.create_repository(repository, 'A curated list of my GitHub stars!')
            rep.create_file(filename, 'starred initial commit', file_value)
        click.launch(rep.html_url)


if __name__ == '__main__':
    starred()