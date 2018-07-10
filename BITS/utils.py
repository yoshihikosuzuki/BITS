import os
import sys
import subprocess
from interval import interval
from logzero import logger


def run_command(command):
    """
    General-purpose command executer.
    """

    try:
        out = subprocess.check_output(command, shell=True)
    except subprocess.CalledProcessError as proc:
        logger.error(proc.output.decode('utf-8'))
        sys.exit(1)
    else:
        return out.decode('utf-8')


def generate_script(template_script_name, args=()):
    """
    Generate an executable bash script using a template bundled with BITS.
    This is basically called from BITS' internal functions.
    """

    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", template_script_name)

    if not os.path.isfile(script_path):
        logger.error("Script file not found")
        sys.exit(1)

    # Replace arguments in the template
    command = f"cat {script_path}"
    for i, arg in enumerate(args, 1):
        command += f" | sed -e 's/\${i}/{arg}/g'"
    command += f" > {template_script_name}"
    run_command(command)


def sge_nize(in_script_name, job_name="run_script", out_log="sge.log", n_core=1, sync=True):
    """
    Add headers for qsub of SGE.
    """

    print(n_core)

    with open(in_script_name + ".qsub", 'w') as out:
        out.write(
f"""#$ -N {job_name}
#$ -o {out_log}
#$ -j y
#$ -S /bin/bash
#$ -cwd
#$ -V
#$ -pe smp {n_core}
#$ -sync {"y" if sync is True else "n"}
""")

        with open(in_script_name, 'r') as f:
            out.write(f.read())


def slurm_nize(in_script_name, job_name="run_script", out_log="sbatch_stdout", err_log="sbatch_stderr", n_core=1, time_limit="24:00:00", mem_per_cpu=1024, partition="batch", wait=True):
    """
    Add headers for sbatch of SLURM.
    """

    with open(in_script_name + ".slurm", 'w') as out:
        out.write(
f"""#SBATCH -J {job_name}
#SBATCH -o {out_log}
#SBATCH -e {err_log}
#SBATCH -n 1
#SBATCH -N 1
#SBATCH -c {n_core}
#SBATCH -t {time_limit}
#SBATCH --mem-per-cpu={mem_per_cpu}
#SBATCH --partition={partition}
{"#SBATCH --wait" if wait is True else ""}
""")

        with open(in_script_name, 'r') as f:
            out.write(f.read())


def make_line(x0, y0, x1, y1, col, width):
    """
    For Plotly.
    Create a line-shape object for Plotly.
    """

    return {'type': 'line', 'xref': 'x', 'yref': 'y',
            'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
            'line': {'color': col, 'width': width}}


def interval_len(intvls):
    """
    For pyinterval (https://pyinterval.readthedocs.io/en/latest/), a module for interval.
    Return the sum of the lengths of the intervals in the given interval object.
    """
    
    ret = 0
    for intvl in intvls.components:
        ret += intvl[0][1] - intvl[0][0] + 1
    return ret


def subtract_interval(a_interval, b_interval, length_threshold=0):
    """
    For pyinterval.
    Calculate A - B, where A and B are interval objects.
    Afterwards, remove remaining intervals whose length are less than <length_threshold>.
    """
    
    ret_interval = interval()
    intersection = a_interval & b_interval
    a_index = 0
    i_index = 0

    flag_load_new_interval = True
    while a_index < len(a_interval) and i_index < len(intersection):
        if flag_load_new_interval:
            a_intvl = a_interval[a_index]
        else:
            flag_load_new_interval = False

        if a_intvl[1] < intersection[i_index][0]:
            ret_interval |= interval(a_intvl)
            a_index += 1
        elif a_intvl[0] > intersection[i_index][1]:
            i_index += 1
        else:
            a_start, a_end = a_intvl
            i_start, i_end = intersection[i_index]
            start_contained = True if min(a_start, i_start) == i_start else False
            end_contained = True if max(a_end, i_end) == i_end else False
            if start_contained:
                if end_contained:
                    a_index += 1
                    i_index += 1
                else:
                    # the tail interval that did not intersect
                    # with this B-interval (but maybe with the next B-interval)
                    a_intvl = interval[i_end + 1, a_end]
                    flag_load_new_interval = False
                    i_index += 1
            else:
                if end_contained:
                    ret_interval |= interval[a_start, i_start - 1]
                    a_index += 1
                else:
                    ret_interval |= interval[a_start, i_start - 1]
                    a_intvl = interval[i_end + 1, a_end]
                    flag_load_new_interval = False
                    i_index += 1
    if not flag_load_new_interval:   # add a tail interval if it exists
        ret_interval |= interval(a_intvl)
        a_index += 1
    while a_index < len(a_interval):   # add remaining intervals in A
        ret_interval |= interval(a_interval[a_index])
        a_index += 1

    ret_interval_long = interval()   # length threshold
    for intvl in ret_interval.components:
        if interval_len(intvl) >= length_threshold:
            ret_interval_long |= intvl

    return ret_interval_long
