from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
import time

QUERY = gql("""
    query ($username: String!, $after: String) {
    user(login: $username) {
        starredRepositories(first: 100, after: $after, orderBy: {direction: DESC, field: STARRED_AT}) {
          totalCount
          nodes {
            name
            nameWithOwner
            description
            url
            stargazerCount
            forkCount
            isPrivate
            pushedAt
            updatedAt
            owner {
              login
            }
            languages(first: 1, orderBy: {field: SIZE, direction: DESC}) {
              edges {
                node {
                  id
                  name
                }
              }
            }
            repositoryTopics(first: 100) {
              nodes {
                topic {
                  name
                  stargazerCount
                }
              }
            }
          }
          pageInfo {
            endCursor
            hasNextPage
          }
        }
      }
    }
    """
            )


class Repository:
    def __init__(self, name, full_name, description, language, url, stargazer_count, is_private, topics, owner, updated_at):
        self.name = name
        self.full_name = full_name
        self.description = description
        self.language = language
        self.url = url
        self.stargazer_count = stargazer_count
        self.is_private = is_private
        self.topics = topics
        self.owner = owner
        self.updated_at = updated_at


class GitHubGQL:
    API_URL = "https://api.github.com/graphql"

    def __init__(self, token):
        self.token = token
        headers = {"Authorization": f"Bearer {token}"}
        
        self.transport = RequestsHTTPTransport(
            url=self.API_URL, 
            headers=headers,
            use_json=True
        )
        self.client = Client(transport=self.transport, fetch_schema_from_transport=False)

    def _execute_with_retry(self, query, variables, max_retries=3):
        """Execute query with retry on server errors."""
        for attempt in range(max_retries):
            try:
                return self.client.execute(query, variable_values=variables)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                if '502' in str(e) or '503' in str(e) or '504' in str(e):
                    time.sleep(2 ** attempt)
                    continue
                raise

    def get_user_starred_by_username(self, username: str, after: str = '', topic_stargazer_count_limit: int = 0):
        items = []
        result = self._execute_with_retry(QUERY, {"username": username, "after": after})

        has_next = result['user']['starredRepositories']['pageInfo']['hasNextPage']
        end_cursor = result['user']['starredRepositories']['pageInfo']['endCursor']
        # total_count = result['user']['starredRepositories']['totalCount']
        for repo in result['user']['starredRepositories']['nodes']:
            name = repo['nameWithOwner']
            full_name = repo['nameWithOwner']
            description = repo['description'] if repo['description'] else ''
            language = repo['languages']['edges'][0]['node']['name'] if repo['languages']['edges'] else ''
            url = repo['url']
            stargazer_count = repo['stargazerCount']
            is_private = repo['isPrivate']
            owner = repo['owner']['login'] if repo['owner'] else ''
            updated_at = repo['updatedAt'] if repo['updatedAt'] else ''
            topics = [tag['topic']['name'] for tag in repo['repositoryTopics']['nodes'] if tag['topic']['stargazerCount'] > topic_stargazer_count_limit]
            items.append(Repository(name, full_name, description, language, url, stargazer_count, is_private, topics, owner, updated_at))

        if has_next:
            items.extend(self.get_user_starred_by_username(username, end_cursor, topic_stargazer_count_limit))
        return items