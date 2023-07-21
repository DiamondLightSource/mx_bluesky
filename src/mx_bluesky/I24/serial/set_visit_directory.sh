#!/bin/bash

# Set visit directory for current experiment type
visit=$1
expt_type=${2:-FT}

ex_pv=BL24I-EA-IOC-12:GP1
ft_pv=ME14E-MO-IOC-01:GP100

shopt -s nocasematch

if [[ $expt_type == "FT" ]] || [[ $expt_type == "fixed-target" ]]
then
    echo "Setting visit PV for serial fixed-target collection."
    caput  $ft_pv $visit
    echo "Visit set to: $visit."
elif [[ $expt_type == "EX" ]] || [[ $expt_type == "extruder" ]]
then
    echo "Setting visit PV for serial extruder collection."
    caput  $ex_pv $visit
    echo "Visit set to: $visit"
else
    echo "Unknown experiment type, visit PV not set."
fi