import os
import pandas as pd
from datetime import datetime
from warcio.archiveiterator import ArchiveIterator
from urllib.parse import urlparse
import re

def parse_warc_file(file_path):
    extracted_data = []
    try:
        with open(file_path, 'rb') as stream:
            for record in ArchiveIterator(stream):
                if record.rec_type == 'response':
                    try:
                        fetched_at = record.rec_headers.get_header('WARC-Date')
                        uri = record.rec_headers.get_header('WARC-Target-URI')
                        domain = urlparse(uri).netloc if uri else ''
                        http_code = ''
                        user_agents = {}
                        current_user_agent = ''

                        content = record.content_stream().read().decode('utf-8', 'ignore')
                        lines = content.split('\n')

                        http_code_match = re.search(r'HTTP/\d\.\d (\d{3})', content)
                        if http_code_match:
                            http_code = http_code_match.group(1)
                            if http_code != '200':
                                continue

                        for line in lines:
                            if line.startswith('User-agent:'):
                                current_user_agent = line.split(': ')[1].strip()
                                user_agents[current_user_agent] = {'disallow_cnt': 0, 'allow_cnt': 0}
                            elif 'Disallow:' in line:
                                user_agents[current_user_agent]['disallow_cnt'] += 1
                            elif 'Allow:' in line:
                                user_agents[current_user_agent]['allow_cnt'] += 1

                        for agent, counts in user_agents.items():
                            extracted_data.append([fetched_at, http_code, domain, agent, counts['disallow_cnt'], counts['allow_cnt']])
                    except Exception as e:
                        print(f"Error processing record: {e}")
    except IOError as e:
        print(f"Error opening file: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    return extracted_data

def compute_statistics(extracted_data, statistics_directory):
    try:
        df = pd.DataFrame(extracted_data, columns=['fetched_at', 'http_code', 'domain', 'user_agent', 'disallow_cnt', 'allow_cnt'])
        df['fetched_at'] = pd.to_datetime(df['fetched_at']).dt.date
        stats = df.groupby('fetched_at').apply(lambda x: pd.Series({
            'total_errors': (x['http_code'] != '200').sum(),
            'total_ok': (x['http_code'] == '200').sum(),
            'total_distinct_ua': x['user_agent'].nunique(),
            'total_allows': x['allow_cnt'].sum(),
            'total_disallows': x['disallow_cnt'].sum()
        })).reset_index()
        stats_file_path = os.path.join(statistics_directory, 'statistics.parquet')
        stats.to_parquet(stats_file_path, index=False)
    except Exception as e:
        print(f"Error in computing statistics: {e}")

def save_to_parquet(data, file_path):
    df = pd.DataFrame(data, columns=['fetched_at', 'http_code', 'domain', 'user_agent', 'disallow_cnt', 'allow_cnt'])
    df.to_parquet(file_path, index=False)

def main():
    raw_directory = 'data/raw/'
    extracted_directory = 'data/extracted/'
    statistics_directory = 'data/statistics/'

    os.makedirs(extracted_directory, exist_ok=True)
    os.makedirs(statistics_directory, exist_ok=True)

    all_extracted_data = []

    for file in os.listdir(raw_directory):
        if file.endswith('.warc'):
            file_path = os.path.join(raw_directory, file)
            extracted_data = parse_warc_file(file_path)
            all_extracted_data.extend(extracted_data)

            parquet_file_path = os.path.join(extracted_directory, os.path.splitext(file)[0] + '.parquet')
            save_to_parquet(extracted_data, parquet_file_path)

    if all_extracted_data:
        compute_statistics(all_extracted_data, statistics_directory)

if __name__ == "__main__":
    main()


