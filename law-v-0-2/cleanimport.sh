#!/bin/bash
autoflake --remove-all-unused-imports --in-place --recursive .   
isort .