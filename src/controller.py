from argparse import ArgumentParser
from src.vault_engine import VaultEngine
from src.utils import DotEnvSerializer
from src.config import Config
from src.env_compiler import EnvCompiler

class Controller:
    def __init__(self):
        parser = ArgumentParser(description="Env Management CLI")
        parser.add_argument("command", choices=["commit", "push", "pull", "build"])
        parser.add_argument("--pjt", help="Project Name", required=True)
        
        parser.add_argument("--phase", help="Target phase")
        parser.add_argument("--root", default=".", help="Root directory to read .env files from")
        parser.add_argument("--target", default=".env", help="env target file")
        parser.add_argument("--template", default=".env.template", help="env template file")
        
        parser.add_argument("--vault-token", required=True)
        
        args = parser.parse_args()

        vault = VaultEngine(args.pjt, Config.VAULT_URL, args.vault_token)        
        compiler = EnvCompiler(vault=vault, serializer=DotEnvSerializer())
        args.phase = args.phase or Config.MAPPER_TO_PHASE[args.target]

        if args.command == "commit":
            compiler.commit(args.phase, args.target, args.root)
            compiler.render(args.phase, args.template, args.root)
        elif args.command == "push":
            compiler.commit(args.phase, args.target, args.root)
        elif args.command == "pull":
            compiler.pull(args.phase, args.target, args.template, args.root)
        elif args.command == "build":
            compiler.build(args.phase, args.target, args.template, args.root)