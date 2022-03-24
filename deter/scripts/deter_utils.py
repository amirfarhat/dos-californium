
import time
import polars as pl

class TimerException(Exception):
  """
  Exceptions specific to instances of the `Timer` below
  """
  pass

class Timer:
  """
  Class to aid in timing code
  """
  def __init__(self, start_text, end_text="Time elapsed: {:.4f} seconds", print_header=False, log=True):
    self._start_time_ns = None
    self._start_text = start_text
    self._end_text = end_text
    self.print_header = print_header
    self.log = log

  def start(self):
    if self._start_time_ns is not None:
      raise TimerException(f"Cannot start Timer, because it is already running with start time {self._start_time_ns}.")

    self._start_time_ns = time.perf_counter_ns()
    if self.print_header:
      if self.log:
        print(self._start_text + "...")

  def stop(self):
    if self._start_time_ns is None:
      raise TimerException(f"Cannot stop Timer, because it has not been started.")

    elapsed_time_ns = time.perf_counter_ns() - self._start_time_ns
    self._start_time_ns = None
    return self._start_text + " - " + self._end_text.format(elapsed_time_ns * 1e-9)

  def __enter__(self):
    self.start()
    return self

  def __exit__(self, *args):
    if self.log:
      print(self.stop())

def pl_replace_from_to(column, from_, to_):
  """
  Produces an expression for polars to replace a `from` values
  to `to` values inside a specified column.
  """
  branch = pl.when(pl.col(column) == from_[0]).then(to_[0])
  for (from_value, to_value) in zip(from_, to_):
    branch = branch.when(pl.col(column) == from_value).then(to_value)
  return branch.otherwise(pl.col(column)).alias(column)

def pl_replace(column, mapping):
  from_ = [k for k, _ in sorted(mapping.items())]
  to_   = [v for _, v in sorted(mapping.items())]
  return pl_replace_from_to(column, from_, to_)