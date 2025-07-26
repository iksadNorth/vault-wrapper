class Config:
    VAULT_URL = "http://localhost:8200"
    MAPPER_TO_PHASE = {
        '.env.common':  'common',
        '.env':         'local',
        '.env.dev':     'dev',
        '.env.stage':   'stage',
        '.env.prod':    'prod',
    }
    HIERARCHY_GRAPH = {
        'prod':     'stage',
        'stage':    'dev',
        'dev':      'local',
    }