"""
A command line over the pick'em scoring arithmetic.

Scores and a strategy go in as JSON; weights, ranks and points come out. No
database, no server, no clock — none of that is arithmetic.

It exists because the guarantee the whole design rests on — a contest
contributes exactly its budget — is a thing you should be able to watch happen
on your own data in one command, rather than take on trust from a README.

Depends on sportspicker-core and nothing else, so it runs anywhere the library
does, including inside an offline sandbox.
"""
__all__ = ["main"]

from .main import main
