const https = require('https');
const fs = require('fs');
const { execSync } = require('child_process');

const USERNAME = process.env.USERNAME;
const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
const COMMIT_MSG = process.env.COMMIT_MSG || 'docs: update stars';

async function fetchStars(username, token, page = 1) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'api.github.com',
      path: `/users/${username}/starred?per_page=200&page=${page}`,
      headers: {
        'User-Agent': 'awesome-stars',
        'Authorization': `token ${token}`
      }
    };

    https.get(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        const link = res.headers.link;
        const hasNext = link && link.includes('rel="next"');
        resolve({ data: JSON.parse(data), hasNext });
      });
    }).on('error', reject);
  });
}

async function getAllStars(username, token) {
  const allStars = [];
  let page = 1;
  let hasNext = true;

  while (hasNext) {
    const { data, hasNext: next } = await fetchStars(username, token, page);
    allStars.push(...data);
    hasNext = next;
    page++;
  }

  return allStars;
}

function groupByLanguage(stars) {
  const grouped = {};
  
  stars.forEach(repo => {
    const lang = repo.language || 'Others';
    if (!grouped[lang]) grouped[lang] = [];
    
    grouped[lang].push({
      name: repo.name,
      url: repo.html_url,
      description: (repo.description || '').replace(/\|/g, '\\|').replace(/\n/g, ' '),
      owner: repo.owner.login,
      stars: repo.stargazers_count
    });
  });

  return Object.keys(grouped).sort().reduce((acc, key) => {
    acc[key] = grouped[key];
    return acc;
  }, {});
}

function generateReadme(grouped, total) {
  const date = new Date().toISOString().split('T')[0];
  const languages = Object.keys(grouped);
  
  let md = `# Awesome Stars [![Awesome](https://cdn.rawgit.com/sindresorhus/awesome/d7305f38d29fed78fa85652e3a63e154dd8e8829/media/badge.svg)](https://github.com/sindresorhus/awesome)\n\n`;
  md += `> A curated list of my GitHub stars!\n\n`;
  md += `![Total](https://img.shields.io/badge/Total-${total}-green.svg)\n`;
  md += `![Updated](https://img.shields.io/badge/Updated-${date}-blue.svg)\n\n`;
  md += `## 🏠 Contents\n\n`;
  
  languages.forEach(lang => {
    const anchor = lang.toLowerCase().replace(/[^\w\- ]+/g, '').replace(/\s/g, '-');
    md += `- [${lang} (${grouped[lang].length})](#${anchor})\n`;
  });
  
  Object.entries(grouped).forEach(([lang, repos]) => {
    md += `\n## ${lang}\n\n`;
    md += `|  | Name | Description | Author | Stars |\n`;
    md += `|---|---|---|---|---|\n`;
    
    repos.forEach((repo, idx) => {
      md += `| ${idx + 1} | [${repo.name}](${repo.url}) | ${repo.description} | ${repo.owner} | ${repo.stars} |\n`;
    });
    
    md += `\n**[⬆ Back to Index](#-contents)**\n`;
  });
  
  md += `\n## 📝 License\n\n`;
  md += `To the extent possible under law, [${USERNAME}](https://github.com/${USERNAME}) has waived all copyright and related or neighboring rights to this work.\n`;
  
  return md;
}

(async () => {
  console.log('Fetching starred repositories...');
  const stars = await getAllStars(USERNAME, GITHUB_TOKEN);
  console.log(`Fetched ${stars.length} repositories`);
  
  const grouped = groupByLanguage(stars);
  const readme = generateReadme(grouped, stars.length);
  
  fs.writeFileSync('README.md', readme);
  console.log('README.md generated');
  
  execSync('git add README.md');
  
  try {
    execSync('git diff --cached --quiet', { stdio: 'ignore' });
    console.log('No changes to commit');
  } catch (e) {
    execSync(`git commit -m "${COMMIT_MSG}"`);
    execSync('git push');
    console.log('Changes pushed');
  }
})();
