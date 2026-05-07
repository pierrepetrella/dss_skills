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


    # Create webapp
    webapp = project.create_webapp(args.webapp_name, "STANDARD")

    # Get state
    state = webapp.get_state()
    
    # Set Flask backend
    settings = webapp.get_settings()
    settings.data["params"]["backendEnabled"] = True
    #settings.data["params"]["envSelection"] = {'envMode': 'EXPLICIT_ENV','envName': 'General_webapp_backend'}
    settings.data["params"]["envSelection"] = {'envMode': 'INHERIT'}
    settings.save()


    return json.dumps({
        "ok": True,
        "created": True,
        "webapp_name": args.webapp_name,
       "state": state.state
    }, indent=2)


if __name__ == "__main__":
    main()
