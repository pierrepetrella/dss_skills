#!/usr/bin/env python3
import argparse
import json
import os
import sys

import dataiku


def main():
    parser = argparse.ArgumentParser(
        description="Create a Dataiku webapp and return its status"
    )
    parser.add_argument("webapp_name", help="Name of the webapp to create")
    args = parser.parse_args()


    client = dataiku.api_client()
    project = client.get_default_project()

    try:
        # Create webapp
        webapp = project.create_webapp(args.webapp_name, "STANDARD")

        # Get state
        state = webapp.get_state()

        print(json.dumps({
            "ok": True,
            "created": True,
            "webapp_name": args.webapp_name,
            "webapp_id": webapp.id,
            "running": state.running,
           "state": state.state
        }, indent=2))

    except Exception as e:
        print("Dataiku cannot create a webapp programatically, please create webapp manually")
        #print(json.dumps({
        #    "ok": False,
        #    "created": False,
        #    "webapp_name": args.webapp_name,
        #    "error": str(e)
        #}))
        sys.exit(1)


if __name__ == "__main__":
    main()
