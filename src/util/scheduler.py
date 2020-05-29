from dataclasses import dataclass
from typing import Optional, List
from logzero import logger
from .proc import run_command


@dataclass(eq=False, frozen=True)
class Scheduler:
    """Utility for submitting scripts using a job scheduler.

    usage:
      > s = Scheduler("sge", "qsub", "all.q")
      > s.submit("sleep 1s", "sleep.sh", "sleep")

    optional variables:
      @ scheduler_name : Name of job scheduler to be used. "sge" or "slurm".
      @ submit_command : Command to submit a job using the scheduler
      @ queue_name     : Queue/partiion name managed by the scheduler.
      @ prefix_command : Commands to be added before the script.
                         Use for environment-related commands:
                         e.g. "source /path/to/venv/bin/activate"
    """
    scheduler_name: str = "sge"
    submit_command: str = "qsub"
    queue_name: Optional[str] = "all.q"
    prefix_command: Optional[str] = None

    def __post_init__(self):
        assert self.scheduler_name in ("sge", "slurm"), "Unsupported scheduler"

    def submit(self,
               script: str,
               out_script_fname: str,
               job_name: str,
               log_fname: str = "log",
               n_core: int = 1,
               max_cpu_hour: Optional[int] = None,
               max_mem_gb: Optional[int] = None,
               depend_job_ids: Optional[List[str]] = None,
               wait: bool = False) -> str:
        """Generate and submit a script file from a script string.

        positional arguments:
          @ script           : Script (not a file).
          @ out_script_fname : Name of the script file generated and submitted.
          @ job_name         : Display name of the job.
          @ log_fname        : Name of the log file.
          @ n_core           : Number of cores used for the job.
          @ max_cpu_hour     : In hours.
          @ max_mem_gb       : In GB.
          @ depend_job_ids   : Wait to start the script until these jobs finish.
          @ wait             : If True, wait until the script finishes.

        return value:
          @ job_id : Of the script submitted.
        """
        logger.info(f"Submit command(s):\n{script}")
        header = (self.gen_sge_header if self.scheduler_name == "sge"
                  else self.gen_slurm_header)(job_name,
                                              log_fname,
                                              n_core,
                                              max_cpu_hour,
                                              max_mem_gb,
                                              depend_job_ids,
                                              wait)
        with open(out_script_fname, "w") as f:
            f.write('\n'.join(filter(None, ["#!/bin/bash",
                                            header + "\n",
                                            self.prefix_command,
                                            script + "\n"])))
        return (run_command(f"{self.submit_command} {out_script_fname}")
                .split()[2 if self.scheduler_name == "sge" else -1])

    def gen_sge_header(self,
                       job_name: str,
                       log_fname: str,
                       n_core: int,
                       max_cpu_hour: Optional[int],
                       max_mem_gb: Optional[int],
                       depend_job_ids: Optional[List[str]],
                       wait: bool) -> str:
        return '\n'.join(filter(None,
                                [f"#$ -N {job_name}",
                                 f"#$ -o {log_fname}",
                                 "#$ -j y",
                                 "#$ -S /bin/bash",
                                 "#$ -cwd",
                                 "#$ -V",
                                 f"#$ -q {self.queue_name}"
                                 if self.queue_name is not None else "",
                                 f"#$ -pe smp {n_core}",
                                 f"#$ -l h_cpu={max_cpu_hour}"
                                 if max_cpu_hour is not None else "",
                                 f"#$ -l mem_total={max_mem_gb}G"
                                 if max_mem_gb is not None else "",
                                 f"#$ -hold_jid {','.join(depend_job_ids)}"
                                 if depend_job_ids is not None else "",
                                 f"#$ -sync {'y' if wait else 'n'}"]))

    def gen_slurm_header(self,
                         job_name: str,
                         log_fname: str,
                         n_core: int,
                         max_cpu_hour: Optional[int],
                         max_mem_gb: Optional[int],
                         depend_job_ids: Optional[List[str]],
                         wait: bool) -> str:
        return '\n'.join(filter(None,
                                [f"#SBATCH -J {job_name}",
                                 f"#SBATCH -o {log_fname}",
                                 f"#SBATCH -p {self.queue_name}"
                                 if self.queue_name is not None else "",
                                 "#SBATCH -n 1",
                                 "#SBATCH -N 1",
                                 f"#SBATCH -c {n_core}",
                                 f"#SBATCH -t '{max_cpu_hour}:00:00'"
                                 if max_cpu_hour is not None else "",
                                 f"#SBATCH --mem={max_mem_gb}G"
                                 if max_mem_gb is not None else "",
                                 f"#SBATCH -d afterany:{','.join(depend_job_ids)}"
                                 if depend_job_ids is not None else "",
                                 "#SBATCH --wait" if wait else ""]))
