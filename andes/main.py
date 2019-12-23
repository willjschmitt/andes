import cProfile
import glob
import logging
import os
import io
import sys
import platform
import pprint
import pstats  # NOQA
from argparse import ArgumentParser
from multiprocessing import Process  # NOQA
from subprocess import call
from time import strftime, sleep

import andes.common.utils
from andes.common.utils import elapsed
from andes.system import System

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def config_logger(logger=None, name='andes', log_file='andes.log', log_path='', stream=True, file=False,
                  stream_level=logging.INFO, file_level=logging.DEBUG):
    """
    Configure a logger for the andes package with options for a `FileHandler`
    and a `StreamHandler`. This function is called at the beginning of
    ``andes.main.main()``.

    Parameters
    ----------
    name : str, optional
        Base logger name, ``andes`` by default. Changing this
        parameter will affect the loggers in modules and
        cause unexpected behaviours.
    log_file : str, optional
        Logg file name for `FileHandler`, ``'andes.log'`` by default.
        If ``None``, the `FileHandler` will not be created.
    log_path : str, optional
        Path to store the log file. By default, the path is generated by
        get_log_dir() in utils.misc.
    stream : bool, optional
        Create a `StreamHandler` for `stdout` if ``True``.
        If ``False``, the handler will not be created.
    stream_level : {10, 20, 30, 40, 50}, optional
        `StreamHandler` verbosity level.

    Returns
    -------
    None

    """
    if not logger:
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

    if not len(logger.handlers):
        if stream is True:
            sh_formatter = logging.Formatter('%(message)s')
            sh = logging.StreamHandler()

            sh.setFormatter(sh_formatter)
            sh.setLevel(stream_level)
            logger.addHandler(sh)

        # file handler for level DEBUG and up
        if file is True and (log_file is not None):
            log_full_path = os.path.join(log_path, log_file)
            fh_formatter = logging.Formatter(
                '%(process)d: %(asctime)s - %(name)s - %(levelname)s - %(message)s')
            fh = logging.FileHandler(log_full_path)
            fh.setLevel(file_level)
            fh.setFormatter(fh_formatter)
            logger.addHandler(fh)
            logger.debug(f'Logging to file {log_full_path}')

        globals()['logger'] = logger


def preamble():
    """
    Log the Andes command-line preamble at the `logging.INFO` level

    Returns
    -------
    None
    """
    from andes import __version__ as version
    logger.info('ANDES {ver} (Build {b}, Python {p} on {os})'
                .format(ver=version[:5], b=version[-8:],
                        p=platform.python_version(),
                        os=platform.system()))
    try:
        username = os.getlogin() + ', '
    except OSError:
        username = ''

    logger.info('Session: {}{}'.format(username, strftime("%m/%d/%Y %I:%M:%S %p")))
    logger.info('')


def cli_parser():
    """
    Construct a CLI argument parser and return the parsed arguments.

    Returns
    -------
    ArgumentParser
        An argument parser for parsing command-line arguments
    """
    parser = ArgumentParser()
    parser.add_argument('filename', help='Case file name', nargs='*')

    # general options
    general_group = parser.add_argument_group('General options')
    general_group.add_argument('-r', '--routine', choices=['tds', 'eig'], help='Routine to run')
    general_group.add_argument('--edit-config', help='Quick edit of the config file',
                               default='', nargs='?', type=str)
    general_group.add_argument('--license', action='store_true', help='Display software license')

    # I/O
    io_group = parser.add_argument_group('I/O options', 'Optional arguments for managing I/Os')
    io_group.add_argument('-p', '--path', help='Path to case files', type=str, default='', dest='input_path')
    io_group.add_argument('-a', '--addfile', help='Additional files used by some formats.')
    io_group.add_argument('-D', '--dynfile', help='Additional dynamic file in dm format.')
    io_group.add_argument('-P', '--pert', help='Perturbation file path', default='')
    io_group.add_argument('-d', '--dump', help='Dump xlsx format case file.', nargs='?', default='')
    io_group.add_argument('-n', '--no-output', help='Force no output of any '
                                                    'kind',
                          action='store_true')
    io_group.add_argument('-o', '--output_path', help='Output path prefix', type=str, default='')
    io_group.add_argument('-C', '--clean', help='Clean output files', action='store_true')

    config_exclusive = parser.add_mutually_exclusive_group()
    config_exclusive.add_argument('--load-config', help='path to the rc config to load',
                                  dest='config')
    config_exclusive.add_argument('--save-config', help='save configuration to file name',
                                  nargs='?', type=str, default='')

    # helps and documentations  TODO
    # group_help = parser.add_argument_group('Help and documentation',
    #                                        'Optional arguments for usage, model and config documentation')
    # group_help.add_argument(
    #     '-g', '--group', help='Show the models in the group.')
    # group_help.add_argument(
    #     '-q', '--quick-help', help='Show a quick help of model format.')
    # group_help.add_argument(
    #     '-c',
    #     '--category',
    #     help='Show model names in the given category.')
    # group_help.add_argument(
    #     '-l',
    #     '--model-list',
    #     help='Show a full list of all models.',
    #     action='store_true')
    # group_help.add_argument(
    #     '-f',
    #     '--model-format',
    #     help='Show the format definition of models.', type=str)
    # group_help.add_argument(
    #     '-Q',
    #     '--model-var',
    #     help='Show the definition of variables <MODEL.VAR>.')
    # group_help.add_argument(
    #     '--config-option', help='Show a quick help of a config option <CONFIG.OPTION>')
    # group_help.add_argument(
    #     '--help-config',
    #     help='Show help of the <CONFIG> class. Use ALL for all configs.')
    # group_help.add_argument(
    #     '-s',
    #     '--search',
    #     help='Search for models that match the pattern.')
    # group_help.add_argument('-e', '--data_example', help='print example parameter of a given model')

    # simulation control
    sim_options = parser.add_argument_group('Simulation control options',
                                            'Overwrites the simulation configs')
    sim_options.add_argument(
        '--dime', help='Specify DiME streaming server address and port')
    sim_options.add_argument(
        '--tf', help='End time of time-domain simulation', type=float)

    # developer options
    dev_group = parser.add_argument_group('Developer options', 'Options for developer debugging')
    dev_group.add_argument(
        '-v',
        '--verbose',
        help='Program logging level.'
             'Available levels are 10-DEBUG, 20-INFO, 30-WARNING, '
             '40-ERROR or 50-CRITICAL. The default level is 20-INFO',
        type=int, default=20, choices=(10, 20, 30, 40, 50))
    dev_group.add_argument(
        '--profile', action='store_true', help='Enable Python cProfiler')
    dev_group.add_argument(
        '--ncpu', help='Number of parallel processes', type=int, default=os.cpu_count())
    dev_group.add_argument('-x', '--exit', help='Exit before running routine', action='store_true')
    dev_group.add_argument('--prepare', help='Prepare the numerical equations and save to file',
                           action='store_true')

    return parser


def edit_conf(edit_config='', load_config=None):
    """
    Edit the Andes config file which occurs first in the search path.

    Parameters
    ----------
    edit_config : bool
        If ``True``, try to open up an editor and edit the config file. Otherwise returns.

    load_config : None or str, optional
        Path to the config file, which will be placed to the first in the search order.

    Returns
    -------
    bool
        ``True`` is a config file is found and an editor is opened. ``False`` if ``edit_config`` is False.
    """
    ret = False

    # no `edit-config` supplied
    if edit_config == '':
        return ret

    conf_path = andes.common.utils.get_config_load_path(load_config)

    if conf_path is not None:
        logger.info('Editing config file {}'.format(conf_path))

        if edit_config is None:
            # use the following default editors
            if platform.system() == 'Linux':
                editor = os.environ.get('EDITOR', 'gedit')
            elif platform.system() == 'Darwin':
                editor = os.environ.get('EDITOR', 'vim')
            elif platform.system() == 'Windows':
                editor = 'notepad.exe'
        else:
            # use `edit_config` as default editor
            editor = edit_config

        call([editor, conf_path])
        ret = True

    else:
        logger.info('Config file does not exist. Save config with \'andes '
                    '--save-config\'')
        ret = True

    return ret


def remove_output():
    """
    Remove the outputs generated by Andes, including power flow reports
    ``_out.txt``, time-domain list ``_out.lst`` and data ``_out.dat``,
    eigenvalue analysis report ``_eig.txt``.

    Returns
    -------
    bool
        ``True`` is the function body executes with success. ``False``
        otherwise.
    """
    found = False
    cwd = os.getcwd()

    for file in os.listdir(cwd):
        if file.endswith('_eig.txt') or \
                file.endswith('_out.txt') or \
                file.endswith('_out.lst') or \
                file.endswith('_out.dat') or \
                file.endswith('_prof.txt'):
            found = True
            try:
                os.remove(file)
                logger.info('<{:s}> removed.'.format(file))
            except IOError:
                logger.error('Error removing file <{:s}>.'.format(file))
    if not found:
        logger.info('no output found in the working directory.')

    return True


def save_config(cf_path=None):
    """
    Save the Andes config to a file at the path specified by ``save_config``.
    The save action will not run if `save_config = ''`.

    Parameters
    ----------
    cf_path : None or str, optional, ('' by default)

        Path to the file to save the config file. If the path is an emtpy
        string, the save action will not run. Save to
        `~/.andes/andes.conf` if ``None``.

    Returns
    -------
    bool
        ``True`` is the save action is run. ``False`` otherwise.
    """
    ret = False

    # no ``--save-config ``
    if cf_path == '':
        return ret

    if cf_path is None:
        cf_path = andes.common.utils.get_config_load_path()

    ps = System()
    ps.save_config(cf_path)
    ret = True

    return ret


def run(case, options=None):
    t0, _ = elapsed()

    if options is None:
        options = {}

    if case is not None:
        options['case'] = case

    # enable profiler if requested
    profile = options.get('profile')
    pr = cProfile.Profile()
    if profile is True:
        pr.enable()

    system = System(options=options)
    system.undill_calls()

    if not andes.io.guess(system):
        return

    if not andes.io.parse(system):
        return

    system.setup()

    if options.get('dump', '') != '':
        andes.io.xlsx.write(system, system.files.dump)

    if options.get('exit'):
        return system

    system.PFlow.nr()

    routine = options.get('routine')
    if routine == 'tds':
        system.TDS.run_implicit()
    elif routine == 'eig':
        system.EIG.run()

    # Disable profiler and output results
    if profile:
        pr.disable()

        if system.files.no_output:
            nlines = 40
            s = io.StringIO()
            ps = pstats.Stats(pr, stream=sys.stdout).sort_stats('cumtime')
            ps.print_stats(nlines)
            logger.info(s.getvalue())
            s.close()
        else:
            nlines = 999
            with open(system.files.prof, 'w') as s:
                ps = pstats.Stats(pr, stream=s).sort_stats('cumtime')
                ps.print_stats(nlines)
            logger.info(f'cProfile data written to <{system.files.prof}>')

    return system


def main(args=None):
    t0, _ = elapsed()

    # parser command line arguments
    if args is None:
        parser = cli_parser()
        args = vars(parser.parse_args())
    elif not isinstance(args, dict):
        args = vars(args)

    # configure stream handler verbose level
    config_logger(log_path=andes.common.utils.get_log_dir(), file=True, stream=True,
                  stream_level=args.get('verbose', logging.INFO))
    # show preamble
    preamble()

    system = System()
    pkl_path = system.get_pkl_path()

    if args.get('prepare') is True or (not os.path.isfile(pkl_path)):
        system.prepare()
        logger.info('Symbolic to numeric preparation completed.')

    # process non-computational command-line arguments and exit
    logger.debug('command line arguments:')
    logger.debug(pprint.pformat(args))

    if edit_conf(args['edit_config']):
        return
    if args.get('license'):
        print_license()
        return
    if args.get('clean'):
        remove_output()
        return
    if args.get('save_config') != '':
        save_config(args.get('save_config'))
        return

    # process input files
    filename = args.get('filename', ())
    if isinstance(filename, str):
        filename = [filename]

    if len(filename) == 0:
        logger.info('error: no input file. Try \'andes -h\' for help.')

    # preprocess cli args
    path = args.get('input_path', os.getcwd())

    cases = []

    for file in filename:
        # use absolute path for cases which will be respected by FileMan
        full_paths = os.path.abspath(os.path.join(path, file))
        found = glob.glob(full_paths)
        if len(found) == 0:
            logger.info('error: file {} does not exist.'.format(full_paths))
        else:
            cases += found

    # remove folders and make cases unique
    cases = list(set(cases))
    valid_cases = []
    for case in cases:
        if os.path.isfile(case):
            valid_cases.append(case)

    logger.debug('Found files: ' + pprint.pformat(valid_cases))

    if len(valid_cases) <= 0:
        pass
    elif len(valid_cases) == 1:
        run(valid_cases[0], options=args)
    else:
        ncpu = args.get('ncpu')
        # set verbose level for multi processing
        logger.info('Processing {} jobs on {} CPUs'.format(len(valid_cases), ncpu))
        logger.handlers[0].setLevel(logging.WARNING)

        # start processes
        jobs = []
        for idx, file in enumerate(valid_cases):
            args['pid'] = idx
            job = Process(
                name='Process {0:d}'.format(idx),
                target=run,
                args=(file, args))
            jobs.append(job)
            job.start()

            start_msg = 'Process {:d} <{:s}> started.'.format(idx, file)
            print(start_msg)
            logger.debug(start_msg)

            if (idx % ncpu == ncpu - 1) or (idx == len(valid_cases) - 1):
                sleep(0.1)
                for job in jobs:
                    job.join()
                jobs = []

        # restore command line output when all jobs are done
        logger.handlers[0].setLevel(logging.INFO)

    t0, s0 = elapsed(t0)

    if len(valid_cases) == 1:
        logger.info('-> Single process finished in {:s}.'.format(s0))
    elif len(valid_cases) >= 2:
        logger.info('-> Multiple processes finished in {:s}.'.format(s0))


def print_license():
    with open(os.path.join(os.path.dirname(__file__), '..', 'LICENSE'), 'r') as f:
        print(f.read())
    return True


if __name__ == '__main__':
    main()
