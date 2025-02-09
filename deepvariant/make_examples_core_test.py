# Copyright 2017 Google LLC.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from this
#    software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""Tests for deepvariant.make_examples_core."""

import copy
from unittest import mock



from absl import flags
from absl.testing import absltest
from absl.testing import flagsaver
from absl.testing import parameterized
import six

from third_party.nucleus.io import fasta
from third_party.nucleus.io import vcf
from third_party.nucleus.protos import reads_pb2
from third_party.nucleus.protos import reference_pb2
from third_party.nucleus.testing import test_utils
from third_party.nucleus.util import ranges
from third_party.nucleus.util import variant_utils
from deepvariant import dv_constants
from deepvariant import make_examples
from deepvariant import make_examples_core
from deepvariant import testdata
from deepvariant import tf_utils
from deepvariant.labeler import variant_labeler
from deepvariant.protos import deepvariant_pb2
from deepvariant.protos import realigner_pb2

FLAGS = flags.FLAGS


def setUpModule():
  testdata.init()


def _make_contigs(specs):
  """Makes ContigInfo protos from specs.

  Args:
    specs: A list of 2- or 3-tuples. All tuples should be of the same length. If
      2-element, these should be the name and length in basepairs of each
      contig, and their pos_in_fasta will be set to their index in the list. If
      the 3-element, the tuple should contain name, length, and pos_in_fasta.

  Returns:
    A list of ContigInfo protos, one for each spec in specs.
  """
  if specs and len(specs[0]) == 3:
    return [
        reference_pb2.ContigInfo(name=name, n_bases=length, pos_in_fasta=i)
        for name, length, i in specs
    ]
  else:
    return [
        reference_pb2.ContigInfo(name=name, n_bases=length, pos_in_fasta=i)
        for i, (name, length) in enumerate(specs)
    ]


def _from_literals_list(literals, contig_map=None):
  """Makes a list of Range objects from literals."""
  return ranges.parse_literals(literals, contig_map)


def _from_literals(literals, contig_map=None):
  """Makes a RangeSet of intervals from literals."""
  return ranges.RangeSet.from_regions(literals, contig_map)


class MakeExamplesCoreUnitTest(parameterized.TestCase):

  def test_read_write_run_info(self):

    def _read_lines(path):
      with open(path) as fin:
        return list(fin.readlines())

    golden_actual = make_examples_core.read_make_examples_run_info(
        testdata.GOLDEN_MAKE_EXAMPLES_RUN_INFO)
    # We don't really want to inject too much knowledge about the golden right
    # here, so we only use a minimal test that (a) the run_info_filename is
    # a non-empty string and (b) the number of candidates sites in the labeling
    # metrics field is greater than 0. Any reasonable golden output will have at
    # least one candidate variant, and the reader should have filled in the
    # value.
    self.assertNotEmpty(golden_actual.options.run_info_filename)
    self.assertEqual(golden_actual.labeling_metrics.n_candidate_variant_sites,
                     testdata.N_GOLDEN_TRAINING_EXAMPLES)

    # Check that reading + writing the data produces the same lines:
    tmp_output = test_utils.test_tmpfile('written_run_info.pbtxt')
    make_examples_core.write_make_examples_run_info(golden_actual, tmp_output)
    self.assertEqual(
        _read_lines(testdata.GOLDEN_MAKE_EXAMPLES_RUN_INFO),
        _read_lines(tmp_output))

  @parameterized.parameters(
      dict(
          flag_value='CALLING',
          expected=deepvariant_pb2.MakeExamplesOptions.CALLING,
      ),
      dict(
          flag_value='TRAINING',
          expected=deepvariant_pb2.MakeExamplesOptions.TRAINING,
      ),
  )
  def test_parse_proto_enum_flag(self, flag_value, expected):
    enum_pb2 = deepvariant_pb2.MakeExamplesOptions.Mode
    self.assertEqual(
        make_examples_core.parse_proto_enum_flag(enum_pb2, flag_value),
        expected)

  def test_parse_proto_enum_flag_error_handling(self):
    with six.assertRaisesRegex(
        self, ValueError,
        'Unknown enum option "foo". Allowed options are CALLING,TRAINING'):
      make_examples_core.parse_proto_enum_flag(
          deepvariant_pb2.MakeExamplesOptions.Mode, 'foo')

  def test_extract_sample_name_from_reads_single_sample(self):
    mock_sample_reader = mock.Mock()
    mock_sample_reader.header = reads_pb2.SamHeader(
        read_groups=[reads_pb2.ReadGroup(sample_id='sample_name')])
    self.assertEqual(
        make_examples_core.extract_sample_name_from_sam_reader(
            mock_sample_reader), 'sample_name')

  @parameterized.parameters(
      # No samples could be found in the reads.
      dict(samples=[], expected_sample_name=dv_constants.DEFAULT_SAMPLE_NAME),
      # Check that we detect an empty sample name and use default instead.
      dict(samples=[''], expected_sample_name=dv_constants.DEFAULT_SAMPLE_NAME),
      # We have more than one sample in the reads.
      dict(samples=['sample1', 'sample2'], expected_sample_name='sample1'),
  )
  def test_extract_sample_name_from_reads_uses_default_when_necessary(
      self, samples, expected_sample_name):
    mock_sample_reader = mock.Mock()
    mock_sample_reader.header = reads_pb2.SamHeader(read_groups=[
        reads_pb2.ReadGroup(sample_id=sample) for sample in samples
    ])
    self.assertEqual(
        expected_sample_name,
        make_examples_core.extract_sample_name_from_sam_reader(
            mock_sample_reader))

  @flagsaver.flagsaver
  def test_confident_regions(self):
    FLAGS.ref = testdata.CHR20_FASTA
    FLAGS.reads = testdata.CHR20_BAM
    FLAGS.truth_variants = testdata.TRUTH_VARIANTS_VCF
    FLAGS.confident_regions = testdata.CONFIDENT_REGIONS_BED
    FLAGS.mode = 'training'
    FLAGS.examples = ''

    options = make_examples.default_options(add_flags=True)
    confident_regions = make_examples_core.read_confident_regions(options)

    # Our expected intervals, inlined from CONFIDENT_REGIONS_BED.
    expected = _from_literals_list([
        'chr20:10000847-10002407', 'chr20:10002521-10004171',
        'chr20:10004274-10004964', 'chr20:10004995-10006386',
        'chr20:10006410-10007800', 'chr20:10007825-10008018',
        'chr20:10008044-10008079', 'chr20:10008101-10008707',
        'chr20:10008809-10008897', 'chr20:10009003-10009791',
        'chr20:10009934-10010531'
    ])
    # Our confident regions should be exactly those found in the BED file.
    six.assertCountEqual(self, expected, list(confident_regions))

  @flagsaver.flagsaver
  def test_gvcf_output_enabled_is_false_without_gvcf_flag(self):
    FLAGS.mode = 'training'
    FLAGS.gvcf = ''
    FLAGS.reads = ''
    FLAGS.ref = ''
    FLAGS.examples = ''
    options = make_examples.default_options(add_flags=True)
    self.assertFalse(make_examples_core.gvcf_output_enabled(options))

  @flagsaver.flagsaver
  def test_gvcf_output_enabled_is_true_with_gvcf_flag(self):
    FLAGS.mode = 'training'
    FLAGS.gvcf = '/tmp/foo.vcf'
    FLAGS.reads = ''
    FLAGS.ref = ''
    FLAGS.examples = ''
    options = make_examples.default_options(add_flags=True)
    self.assertTrue(make_examples_core.gvcf_output_enabled(options))

  def test_validate_ref_contig_coverage(self):
    ref_contigs = _make_contigs([('1', 100), ('2', 100)])

    # Fully covered reference contigs don't trigger an error.
    for threshold in [0.5, 0.9, 1.0]:
      self.assertIsNone(
          make_examples_core.validate_reference_contig_coverage(
              ref_contigs, ref_contigs, threshold))

    # No common contigs always blows up.
    for threshold in [0.0, 0.1, 0.5, 0.9, 1.0]:
      with six.assertRaisesRegex(self, ValueError, 'span 200'):
        make_examples_core.validate_reference_contig_coverage(
            ref_contigs, [], threshold)

    # Dropping either contig brings up below our 0.9 threshold.
    with six.assertRaisesRegex(self, ValueError, 'span 200'):
      make_examples_core.validate_reference_contig_coverage(
          ref_contigs, _make_contigs([('1', 100)]), 0.9)

    with six.assertRaisesRegex(self, ValueError, 'span 200'):
      make_examples_core.validate_reference_contig_coverage(
          ref_contigs, _make_contigs([('2', 100)]), 0.9)

    # Our actual overlap is 50%, so check that we raise when appropriate.
    with six.assertRaisesRegex(self, ValueError, 'span 200'):
      make_examples_core.validate_reference_contig_coverage(
          ref_contigs, _make_contigs([('2', 100)]), 0.6)
    self.assertIsNone(
        make_examples_core.validate_reference_contig_coverage(
            ref_contigs, _make_contigs([('2', 100)]), 0.4))

  @parameterized.parameters(
      # all intervals are shared.
      ([[('chrM', 10)], [('chrM', 10)]], [('chrM', 10)]),
      # No common intervals.
      ([[('chrM', 10)], [('chr1', 10)]], []),
      # The names are the same but sizes are different, so not common.
      ([[('chrM', 10)], [('chrM', 20)]], []),
      # One common interval and one not.
      ([[('chrM', 10), ('chr1', 20)], [('chrM', 10),
                                       ('chr2', 30)]], [('chrM', 10)]),
      # Check that the order doesn't matter.
      ([[('chr1', 20), ('chrM', 10)], [('chrM', 10),
                                       ('chr2', 30)]], [('chrM', 10, 1)]),
      # Three-way merges.
      ([
          [('chr1', 20), ('chrM', 10)],
          [('chrM', 10), ('chr2', 30)],
          [('chr2', 30), ('chr3', 30)],
      ], []),
  )
  def test_common_contigs(self, contigs_list, expected):
    self.assertEqual(
        _make_contigs(expected),
        make_examples_core.common_contigs(
            [_make_contigs(contigs) for contigs in contigs_list]))

  @parameterized.parameters(
      # Note that these tests aren't so comprehensive as we are trusting that
      # the intersection code logic itself is good and well-tested elsewhere.
      # Here we are focusing on some basic tests and handling of missing
      # calling_region and confident_region data.
      (['1:1-10'], ['1:1-10']),
      (['1:1-100'], ['1:1-100']),
      (['1:50-150'], ['1:50-100']),
      (None, ['1:1-100', '2:1-200']),
      (['1:20-50'], ['1:20-50']),
      # Chr3 isn't part of our contigs; make sure we tolerate it.
      (['1:20-30', '1:40-60', '3:10-50'], ['1:20-30', '1:40-60']),
      # Check that we handle overlapping calling or confident regions.
      (['1:25-30', '1:20-40'], ['1:20-40']),
  )
  def test_regions_to_process(self, calling_regions, expected):
    contigs = _make_contigs([('1', 100), ('2', 200)])
    six.assertCountEqual(
        self, _from_literals_list(expected),
        make_examples_core.regions_to_process(
            contigs, 1000, calling_regions=_from_literals(calling_regions)))

  @parameterized.parameters(
      (50, None, [
          '1:1-50', '1:51-100', '2:1-50', '2:51-76', '3:1-50', '3:51-100',
          '3:101-121'
      ]),
      (120, None, ['1:1-100', '2:1-76', '3:1-120', '3:121']),
      (500, None, ['1:1-100', '2:1-76', '3:1-121']),
      (10, ['1:1-20', '1:30-35'], ['1:1-10', '1:11-20', '1:30-35']),
      (8, ['1:1-20', '1:30-35'], ['1:1-8', '1:9-16', '1:17-20', '1:30-35']),
  )
  def test_regions_to_process_partition(self, max_size, calling_regions,
                                        expected):
    contigs = _make_contigs([('1', 100), ('2', 76), ('3', 121)])
    six.assertCountEqual(
        self, _from_literals_list(expected),
        make_examples_core.regions_to_process(
            contigs, max_size, calling_regions=_from_literals(calling_regions)))

  @parameterized.parameters(
      dict(includes=[], excludes=[], expected=['1:1-100', '2:1-200']),
      dict(includes=['1'], excludes=[], expected=['1:1-100']),
      # Check that excludes work as expected.
      dict(includes=[], excludes=['1'], expected=['2:1-200']),
      dict(includes=[], excludes=['2'], expected=['1:1-100']),
      dict(includes=[], excludes=['1', '2'], expected=[]),
      # Check that excluding pieces works. The main checks on taking the
      # difference between two RangeSets live in ranges.py so here we are just
      # making sure some basic logic works.
      dict(includes=['1'], excludes=['1:1-10'], expected=['1:11-100']),
      # Check that includes and excludes work together.
      dict(
          includes=['1', '2'],
          excludes=['1:5-10', '1:20-50', '2:10-20'],
          expected=['1:1-4', '1:11-19', '1:51-100', '2:1-9', '2:21-200']),
      dict(
          includes=['1'],
          excludes=['1:5-10', '1:20-50', '2:10-20'],
          expected=['1:1-4', '1:11-19', '1:51-100']),
      dict(
          includes=['2'],
          excludes=['1:5-10', '1:20-50', '2:10-20'],
          expected=['2:1-9', '2:21-200']),
      # A complex example of including and excluding.
      dict(
          includes=['1:10-20', '2:50-60', '2:70-80'],
          excludes=['1:1-13', '1:19-50', '2:10-65'],
          expected=['1:14-18', '2:70-80']),
  )
  def test_build_calling_regions(self, includes, excludes, expected):
    contigs = _make_contigs([('1', 100), ('2', 200)])
    actual = make_examples_core.build_calling_regions(contigs, includes,
                                                      excludes)
    six.assertCountEqual(self, actual, _from_literals_list(expected))

  def test_regions_to_process_sorted_within_contig(self):
    # These regions are out of order but within a single contig.
    contigs = _make_contigs([('z', 100)])
    in_regions = _from_literals(['z:15', 'z:20', 'z:6', 'z:25-30', 'z:3-4'])
    sorted_regions = _from_literals_list(
        ['z:3-4', 'z:6', 'z:15', 'z:20', 'z:25-30'])
    actual_regions = list(
        make_examples_core.regions_to_process(
            contigs, 100, calling_regions=in_regions))
    # The assertEqual here is checking the order is exactly what we expect.
    self.assertEqual(sorted_regions, actual_regions)

  def test_regions_to_process_sorted_contigs(self):
    # These contig names are out of order lexicographically.
    contigs = _make_contigs([('z', 100), ('a', 100), ('n', 100)])
    in_regions = _from_literals(['a:10', 'n:1', 'z:20', 'z:5'])
    sorted_regions = _from_literals_list(['z:5', 'z:20', 'a:10', 'n:1'])
    actual_regions = list(
        make_examples_core.regions_to_process(
            contigs, 100, calling_regions=in_regions))
    # The assertEqual here is checking the order is exactly what we expect.
    self.assertEqual(sorted_regions, actual_regions)

  @parameterized.parameters([2, 3, 4, 5, 50])
  def test_regions_to_process_sharding(self, num_shards):
    """Makes sure we deterministically split up regions."""

    def get_regions(task_id, num_shards):
      return make_examples_core.regions_to_process(
          contigs=_make_contigs([('z', 100), ('a', 100), ('n', 100)]),
          partition_size=5,
          task_id=task_id,
          num_shards=num_shards)

    # Check that the regions are the same unsharded vs. sharded.
    unsharded_regions = get_regions(0, 0)
    sharded_regions = []
    for task_id in range(num_shards):
      task_regions = get_regions(task_id, num_shards)
      sharded_regions.extend(task_regions)
    six.assertCountEqual(self, unsharded_regions, sharded_regions)

  @parameterized.parameters(
      # Providing one of task id and num_shards but not the other is bad.
      (None, 0),
      (None, 2),
      (2, None),
      (0, None),
      # Negative values are illegal.
      (-1, 2),
      (0, -2),
      # task_id >= num_shards is bad.
      (2, 2),
      (3, 2),
  )
  def test_regions_to_process_fails_with_bad_shard_args(self, task, num_shards):
    with self.assertRaises(ValueError):
      make_examples_core.regions_to_process(
          contigs=_make_contigs([('z', 100), ('a', 100), ('n', 100)]),
          partition_size=10,
          task_id=task,
          num_shards=num_shards)

  @parameterized.parameters(
      # Fetch all positions
      (['chr20:1-20000000'], 221),
      # Fetch subset of positions
      (['chr20:1-10003021'], 20),
  )
  def test_fetch_vcf_positions(self, calling_regions, expected_count):
    contigs = _make_contigs([('chr20', 20000000)])
    calling_regions = _from_literals(calling_regions)
    variant_positions = make_examples_core.fetch_vcf_positions(
        [testdata.TRUTH_VARIANTS_VCF], contigs, calling_regions)
    self.assertLen(variant_positions, expected_count)

  @parameterized.parameters(
      # One variant in region.
      (['x:100-200'], ['x:150-151'], [0]),
      # Different chromosomes.
      (['x:100-200'], ['y:150-151'], []),
      # A variant at the beginning of a region.
      (['x:100-200', 'x:201-300'], ['x:100-101'], [0]),
      (['x:1-10', 'x:11-20', 'x:21-30'], ['x:11-12'], [1]),
      # A variant before all the regions.
      (['x:11-20', 'x:20-30'], ['x:1-2'], []),
      # A variant after all the regions.
      (['x:1-10', 'x:11-20', 'x:21-30'], ['x:40-50'], []),
      # Multiple variants in the same region.
      (['x:11-20', 'x:21-30'
       ], ['x:1-2', 'x:25-26', 'x:25-26', 'x:26-27', 'x:40-50'], [1]),
      # A variant spanning multiple regions belongs where it starts.
      (['x:1-10', 'x:11-20', 'x:21-30', 'x:31-40', 'x:41-50', 'x:51-60'
       ], ['x:15-66'], [1]),
  )
  def test_filter_regions_by_vcf(self, region_literals, variant_literals,
                                 regions_to_keep):
    regions = [ranges.parse_literal(l) for l in region_literals]
    variant_positions = [ranges.parse_literal(l) for l in variant_literals]
    output = make_examples_core.filter_regions_by_vcf(regions,
                                                      variant_positions)
    list_output = list(output)
    list_expected = [regions[i] for i in regions_to_keep]
    self.assertEqual(list_output, list_expected)

  @parameterized.parameters(
      dict(
          ref_names=['1', '2', '3'],
          sam_names=['1', '2', '3'],
          vcf_names=None,
          names_to_exclude=[],
          min_coverage_fraction=1.0,
          expected_names=['1', '2', '3']),
      dict(
          ref_names=['1', '2', '3'],
          sam_names=['1', '2'],
          vcf_names=None,
          names_to_exclude=[],
          min_coverage_fraction=0.66,
          expected_names=['1', '2']),
      dict(
          ref_names=['1', '2', '3'],
          sam_names=['1', '2'],
          vcf_names=['1', '3'],
          names_to_exclude=[],
          min_coverage_fraction=0.33,
          expected_names=['1']),
      dict(
          ref_names=['1', '2', '3', '4', '5'],
          sam_names=['1', '2', '3'],
          vcf_names=None,
          names_to_exclude=['4', '5'],
          min_coverage_fraction=1.0,
          expected_names=['1', '2', '3']),
  )
  def test_ensure_consistent_contigs(self, ref_names, sam_names, vcf_names,
                                     names_to_exclude, min_coverage_fraction,
                                     expected_names):
    ref_contigs = _make_contigs([(name, 100) for name in ref_names])
    sam_contigs = _make_contigs([(name, 100) for name in sam_names])
    if vcf_names is not None:
      vcf_contigs = _make_contigs([(name, 100) for name in vcf_names])
    else:
      vcf_contigs = None
    actual = make_examples_core._ensure_consistent_contigs(
        ref_contigs, sam_contigs, vcf_contigs, names_to_exclude,
        min_coverage_fraction)
    self.assertEqual([a.name for a in actual], expected_names)

  @parameterized.parameters(
      dict(
          ref_names=['1', '2', '3'],
          sam_names=['1', '2'],
          vcf_names=None,
          names_to_exclude=[],
          min_coverage_fraction=0.67),
      dict(
          ref_names=['1', '2', '3'],
          sam_names=['1', '2'],
          vcf_names=['1', '3'],
          names_to_exclude=[],
          min_coverage_fraction=0.34),
  )
  def test_ensure_inconsistent_contigs(self, ref_names, sam_names, vcf_names,
                                       names_to_exclude, min_coverage_fraction):
    ref_contigs = _make_contigs([(name, 100) for name in ref_names])
    sam_contigs = _make_contigs([(name, 100) for name in sam_names])
    if vcf_names is not None:
      vcf_contigs = _make_contigs([(name, 100) for name in vcf_names])
    else:
      vcf_contigs = None
    with six.assertRaisesRegex(self, ValueError, 'Reference contigs span'):
      make_examples_core._ensure_consistent_contigs(ref_contigs, sam_contigs,
                                                    vcf_contigs,
                                                    names_to_exclude,
                                                    min_coverage_fraction)

  @flagsaver.flagsaver
  def test_regions_and_exclude_regions_flags(self):
    FLAGS.mode = 'calling'
    FLAGS.ref = testdata.CHR20_FASTA
    FLAGS.reads = testdata.CHR20_BAM
    FLAGS.regions = 'chr20:10,000,000-11,000,000'
    FLAGS.examples = 'examples.tfrecord'
    FLAGS.exclude_regions = 'chr20:10,010,000-10,100,000'

    options = make_examples.default_options(add_flags=True)
    six.assertCountEqual(
        self,
        list(
            ranges.RangeSet(
                make_examples_core.processing_regions_from_options(options))),
        _from_literals_list(
            ['chr20:10,000,000-10,009,999', 'chr20:10,100,001-11,000,000']))

  @flagsaver.flagsaver
  def test_incorrect_empty_regions(self):
    FLAGS.mode = 'calling'
    FLAGS.ref = testdata.CHR20_FASTA
    FLAGS.reads = testdata.CHR20_BAM
    # Deliberately incorrect contig name.
    FLAGS.regions = '20:10,000,000-11,000,000'
    FLAGS.examples = 'examples.tfrecord'

    options = make_examples.default_options(add_flags=True)
    with six.assertRaisesRegex(self, ValueError,
                               'The regions to call is empty.'):
      make_examples_core.processing_regions_from_options(options)


class RegionProcessorTest(parameterized.TestCase):

  def setUp(self):
    super(RegionProcessorTest, self).setUp()
    self._saved_flags = flagsaver.save_flag_values()
    self.region = ranges.parse_literal('chr20:10,000,000-10,000,100')

    FLAGS.reads = ''
    self.options = make_examples.default_options(add_flags=False)
    self.options.reference_filename = testdata.CHR20_FASTA
    main_sample = self.options.sample_options[0]
    if not main_sample.reads_filenames:
      main_sample.reads_filenames.append(testdata.CHR20_BAM)
    main_sample.variant_caller_options.sample_name = 'sample_id'
    main_sample.name = 'sample_id'
    self.options.truth_variants_filename = testdata.TRUTH_VARIANTS_VCF
    self.options.mode = deepvariant_pb2.MakeExamplesOptions.TRAINING
    self.processor = make_examples_core.RegionProcessor(self.options)
    self.ref_reader = fasta.IndexedFastaReader(self.options.reference_filename)
    self.mock_init = self.add_mock('initialize')
    for sample in self.processor.samples:
      sample.in_memory_sam_reader = mock.Mock()
    self.default_shape = [5, 5, 7]
    self.default_format = 'raw'

  def tearDown(self):
    super(RegionProcessorTest, self).tearDown()
    flagsaver.restore_flag_values(self._saved_flags)

  def add_mock(self, name, retval='dontadd', side_effect='dontadd'):
    patcher = mock.patch.object(self.processor, name, autospec=True)
    self.addCleanup(patcher.stop)
    mocked = patcher.start()
    if retval != 'dontadd':
      mocked.return_value = retval
    if side_effect != 'dontadd':
      mocked.side_effect = side_effect
    return mocked

  def test_on_demand_initialization_called_if_not_initialized(self):
    candidates = ['Candidates']
    self.assertFalse(self.processor.initialized)
    main_sample = self.processor.samples[0]

    mock_rr = self.add_mock('region_reads', retval=[])
    mock_cir = self.add_mock(
        'candidates_in_region',
        retval=({
            'main_sample': candidates
        }, {
            'main_sample': []
        }))
    mock_lc = self.add_mock('label_candidates', retval=[])
    self.processor.process(self.region)
    test_utils.assert_called_once_workaround(self.mock_init)
    mock_rr.assert_called_once_with(
        region=self.region,
        sam_readers=None,
        reads_filenames=main_sample.options.reads_filenames)
    main_sample.in_memory_sam_reader.replace_reads.assert_called_once_with([])
    mock_cir.assert_called_once_with(self.region)
    mock_lc.assert_called_once_with(candidates, self.region)

  def test_on_demand_initialization_not_called_if_initialized(self):
    self.processor.initialized = True
    self.assertTrue(self.processor.initialized)
    main_sample = self.processor.samples[0]
    mock_rr = self.add_mock('region_reads', retval=[])
    mock_cir = self.add_mock(
        'candidates_in_region',
        retval=({
            'main_sample': []
        }, {
            'main_sample': []
        }))
    mock_lc = self.add_mock('label_candidates', retval=[])
    self.processor.process(self.region)
    test_utils.assert_not_called_workaround(self.mock_init)
    mock_rr.assert_called_once_with(
        region=self.region,
        sam_readers=None,
        reads_filenames=main_sample.options.reads_filenames)
    main_sample.in_memory_sam_reader.replace_reads.assert_called_once_with([])
    mock_cir.assert_called_once_with(self.region)
    test_utils.assert_called_once_workaround(mock_lc)

  def test_process_calls_no_candidates(self):
    main_sample = self.processor.samples[0]
    mock_rr = self.add_mock('region_reads', retval=[])
    mock_cir = self.add_mock(
        'candidates_in_region',
        retval=({
            'main_sample': []
        }, {
            'main_sample': []
        }))
    mock_cpe = self.add_mock('create_pileup_examples', retval=[])
    mock_lc = self.add_mock('label_candidates')
    candidates, examples, gvcfs, runtimes = self.processor.process(self.region)
    self.assertEmpty(candidates['main_sample'])
    self.assertEmpty(examples['main_sample'])
    self.assertEmpty(gvcfs['main_sample'])
    self.assertIsInstance(runtimes, dict)
    mock_rr.assert_called_once_with(
        region=self.region,
        sam_readers=None,
        reads_filenames=main_sample.options.reads_filenames)
    main_sample.in_memory_sam_reader.replace_reads.assert_called_once_with([])
    mock_cir.assert_called_once_with(self.region)
    test_utils.assert_not_called_workaround(mock_cpe)
    mock_lc.assert_called_once_with([], self.region)

  @parameterized.parameters([
      deepvariant_pb2.MakeExamplesOptions.TRAINING,
      deepvariant_pb2.MakeExamplesOptions.CALLING
  ])
  def test_process_calls_with_candidates(self, mode):
    self.processor.options.mode = mode

    main_sample = self.processor.samples[0]
    mock_read = mock.MagicMock()
    mock_candidate = mock.MagicMock()
    mock_example = mock.MagicMock()
    mock_label = mock.MagicMock()
    mock_rr = self.add_mock('region_reads', retval=[mock_read])
    mock_cir = self.add_mock(
        'candidates_in_region',
        retval=({
            'main_sample': [mock_candidate]
        }, {
            'main_sample': []
        }))
    mock_cpe = self.add_mock('create_pileup_examples', retval=[mock_example])
    mock_lc = self.add_mock(
        'label_candidates', retval=[(mock_candidate, mock_label)])
    mock_alte = self.add_mock('add_label_to_example', retval=mock_example)
    candidates, examples, gvcfs, runtimes = self.processor.process(self.region)
    self.assertEqual(candidates['main_sample'], [mock_candidate])
    self.assertEqual(examples['main_sample'], [mock_example])
    self.assertEmpty(gvcfs['main_sample'])
    self.assertIsInstance(runtimes, dict)
    mock_rr.assert_called_once_with(
        region=self.region,
        sam_readers=None,
        reads_filenames=main_sample.options.reads_filenames)
    main_sample.in_memory_sam_reader.replace_reads.assert_called_once_with(
        [mock_read])
    mock_cir.assert_called_once_with(self.region)
    mock_cpe.assert_called_once_with(mock_candidate, sample_order=[0])

    if mode == deepvariant_pb2.MakeExamplesOptions.TRAINING:
      mock_lc.assert_called_once_with([mock_candidate], self.region)
      mock_alte.assert_called_once_with(mock_example, mock_label)
    else:
      # In training mode we don't label our candidates.
      test_utils.assert_not_called_workaround(mock_lc)
      test_utils.assert_not_called_workaround(mock_alte)

  @parameterized.parameters([
      deepvariant_pb2.MakeExamplesOptions.TRAINING,
      deepvariant_pb2.MakeExamplesOptions.CALLING
  ])
  def test_process_keeps_ordering_of_candidates_and_examples(self, mode):
    self.processor.options.mode = mode

    r1, r2 = mock.Mock(), mock.Mock()
    c1, c2 = mock.Mock(), mock.Mock()
    l1, l2 = mock.Mock(), mock.Mock()
    e1, e2, e3 = mock.Mock(), mock.Mock(), mock.Mock()
    main_sample = self.processor.samples[0]
    self.add_mock('region_reads', retval=[r1, r2])
    self.add_mock(
        'candidates_in_region',
        retval=({
            'main_sample': [c1, c2]
        }, {
            'main_sample': []
        }))
    mock_cpe = self.add_mock(
        'create_pileup_examples', side_effect=[[e1], [e2, e3]])
    mock_lc = self.add_mock('label_candidates', retval=[(c1, l1), (c2, l2)])
    mock_alte = self.add_mock('add_label_to_example', side_effect=[e1, e2, e3])
    candidates, examples, gvcfs, runtimes = self.processor.process(self.region)
    self.assertEqual(candidates['main_sample'], [c1, c2])
    self.assertEqual(examples['main_sample'], [e1, e2, e3])
    self.assertEmpty(gvcfs['main_sample'])
    self.assertIsInstance(runtimes, dict)
    main_sample.in_memory_sam_reader.replace_reads.assert_called_once_with(
        [r1, r2])
    # We don't try to label variants when in calling mode.
    self.assertEqual(
        [mock.call(c1, sample_order=[0]),
         mock.call(c2, sample_order=[0])], mock_cpe.call_args_list)

    if mode == deepvariant_pb2.MakeExamplesOptions.CALLING:
      # In calling mode, we never try to label.
      test_utils.assert_not_called_workaround(mock_lc)
      test_utils.assert_not_called_workaround(mock_alte)
    else:
      mock_lc.assert_called_once_with([c1, c2], self.region)
      self.assertEqual([
          mock.call(e1, l1),
          mock.call(e2, l2),
          mock.call(e3, l2),
      ], mock_alte.call_args_list)

  def test_process_with_realigner(self):
    self.processor.options.mode = deepvariant_pb2.MakeExamplesOptions.CALLING
    self.processor.options.realigner_enabled = True
    self.processor.options.realigner_options.CopyFrom(
        realigner_pb2.RealignerOptions())
    self.processor.realigner = mock.Mock()
    self.processor.realigner.realign_reads.return_value = [], []

    main_sample = self.processor.samples[0]
    main_sample.sam_readers = [mock.Mock()]
    main_sample.sam_readers[0].query.return_value = []

    c1, c2 = mock.Mock(), mock.Mock()
    e1, e2, e3 = mock.Mock(), mock.Mock(), mock.Mock()
    self.add_mock(
        'candidates_in_region',
        retval=({
            'main_sample': [c1, c2]
        }, {
            'main_sample': []
        }))
    mock_cpe = self.add_mock(
        'create_pileup_examples', side_effect=[[e1], [e2, e3]])
    mock_lc = self.add_mock('label_candidates')

    candidates, examples, gvcfs, runtimes = self.processor.process(self.region)
    self.assertEqual(candidates['main_sample'], [c1, c2])
    self.assertEqual(examples['main_sample'], [e1, e2, e3])
    self.assertEmpty(gvcfs['main_sample'])
    self.assertIsInstance(runtimes, dict)
    main_sample.sam_readers[0].query.assert_called_once_with(self.region)
    self.processor.realigner.realign_reads.assert_called_once_with([],
                                                                   self.region)
    main_sample.in_memory_sam_reader.replace_reads.assert_called_once_with([])
    self.assertEqual(
        [mock.call(c1, sample_order=[0]),
         mock.call(c2, sample_order=[0])], mock_cpe.call_args_list)
    test_utils.assert_not_called_workaround(mock_lc)

  def test_candidates_in_region_no_reads(self):
    main_sample = self.processor.samples[0]
    main_sample.in_memory_sam_reader.query.return_value = []
    mock_ac = self.add_mock('_make_allele_counter_for_region')

    self.assertEqual(({}, {}), self.processor.candidates_in_region(self.region))

    main_sample.in_memory_sam_reader.query.assert_called_once_with(self.region)
    # A region with no reads should return out without making an AlleleCounter.
    test_utils.assert_not_called_workaround(mock_ac)

  @parameterized.parameters(True, False)
  def test_candidates_in_region(self, include_gvcfs):
    self.options.gvcf_filename = 'foo.vcf' if include_gvcfs else ''
    main_sample = self.processor.samples[0]
    reads = ['read1', 'read2']
    main_sample.in_memory_sam_reader.query.return_value = reads

    # Setup our make_allele_counter and other mocks.
    mock_ac = mock.Mock()
    mock_make_ac = self.add_mock(
        '_make_allele_counter_for_region', retval=mock_ac)
    # Setup our make_variant_caller and downstream mocks.
    mock_vc = mock.Mock()
    mock_vc.calls_and_gvcfs.return_value = (['variant'],
                                            ['gvcf'] if include_gvcfs else [])
    main_sample.variant_caller = mock_vc

    actual = self.processor.candidates_in_region(self.region)

    # Make sure we're getting our reads for the region.
    main_sample.in_memory_sam_reader.query.assert_called_once_with(self.region)

    # Make sure we're creating an AlleleCounter once and adding each of our
    # reads to it.
    mock_make_ac.assert_called_once_with(self.region, [])
    self.assertEqual([mock.call(r, 'sample_id') for r in reads],
                     mock_ac.add.call_args_list)

    # Make sure we call CallVariant for each of the counts returned by the
    # allele counter.
    include_med_dp = False
    mock_vc.calls_and_gvcfs.assert_called_once_with(
        allele_counters={'sample_id': mock_ac},
        target_sample='sample_id',
        include_gvcfs=include_gvcfs,
        include_med_dp=include_med_dp)

    # Finally, our actual result should be the single 'variant' and potentially
    # the gvcf records, each organized by sample.
    expected_output = ({
        'main_sample': ['variant']
    }, {
        'main_sample': ['gvcf'] if include_gvcfs else []
    })
    self.assertEqual(expected_output, actual)

  def test_create_pileup_examples_handles_none(self):
    self.processor.pic = mock.Mock()
    self.processor.pic.get_reads.return_value = []
    dv_call = mock.Mock()
    self.processor.pic.create_pileup_images.return_value = None
    self.assertEqual([], self.processor.create_pileup_examples(dv_call))
    self.processor.pic.create_pileup_images.assert_called_once_with(
        dv_call=dv_call,
        reads_for_samples=[[]],
        haplotype_alignments_for_samples=None,
        haplotype_sequences=None,
        sample_order=None)

  def test_create_pileup_examples(self):
    self.processor.pic = mock.Mock()
    self.processor.pic.get_reads.return_value = []
    self.add_mock(
        '_encode_tensor',
        side_effect=[
            (six.b('tensor1'), self.default_shape, self.default_format),
            (six.b('tensor2'), self.default_shape, self.default_format)
        ])
    dv_call = mock.Mock()
    dv_call.variant = test_utils.make_variant(start=10, alleles=['A', 'C', 'G'])
    ex = mock.Mock()
    alt1, alt2 = ['C'], ['G']
    self.processor.pic.create_pileup_images.return_value = [
        (alt1, six.b('tensor1')), (alt2, six.b('tensor2'))
    ]

    actual = self.processor.create_pileup_examples(dv_call)

    self.processor.pic.create_pileup_images.assert_called_once_with(
        dv_call=dv_call,
        reads_for_samples=[[]],
        haplotype_alignments_for_samples=None,
        haplotype_sequences=None,
        sample_order=None)

    self.assertLen(actual, 2)
    for ex, (alt, img) in zip(actual, [(alt1, six.b('tensor1')),
                                       (alt2, six.b('tensor2'))]):
      self.assertEqual(tf_utils.example_alt_alleles(ex), alt)
      self.assertEqual(tf_utils.example_variant(ex), dv_call.variant)
      self.assertEqual(tf_utils.example_encoded_image(ex), img)
      self.assertEqual(tf_utils.example_image_shape(ex), self.default_shape)
      self.assertEqual(
          tf_utils.example_image_format(ex), six.b(self.default_format))

  @parameterized.parameters(
      # Test that a het variant gets a label value of 1 assigned to the example.
      dict(
          label=variant_labeler.VariantLabel(
              is_confident=True,
              variant=test_utils.make_variant(start=10, alleles=['A', 'C']),
              genotype=(0, 1)),
          expected_label_value=1,
      ),
      # Test that a reference variant gets a label value of 0 in the example.
      dict(
          label=variant_labeler.VariantLabel(
              is_confident=True,
              variant=test_utils.make_variant(start=10, alleles=['A', '.']),
              genotype=(0, 0)),
          expected_label_value=0,
      ),
  )
  def test_add_label_to_example(self, label, expected_label_value):
    example = self._example_for_variant(label.variant)
    labeled = copy.deepcopy(example)
    actual = self.processor.add_label_to_example(labeled, label)

    # The add_label_to_example command modifies labeled and returns it.
    self.assertIs(actual, labeled)

    # Check that all keys from example are present in labeled.
    for key, value in example.features.feature.items():
      if key != 'variant/encoded':  # Special case tested below.
        self.assertEqual(value, labeled.features.feature[key])

    # The genotype of our example_variant should be set to the true genotype
    # according to our label.
    self.assertEqual(expected_label_value, tf_utils.example_label(labeled))
    labeled_variant = tf_utils.example_variant(labeled)
    call = variant_utils.only_call(labeled_variant)
    self.assertEqual(tuple(call.genotype), label.genotype)

    # The original variant and labeled_variant from out tf.Example should be
    # equal except for the genotype field, since this is set by
    # add_label_to_example.
    label.variant.calls[0].genotype[:] = []
    call.genotype[:] = []
    self.assertEqual(label.variant, labeled_variant)

  def test_label_variant_raises_for_non_confident_variant(self):
    label = variant_labeler.VariantLabel(
        is_confident=False,
        variant=test_utils.make_variant(start=10, alleles=['A', 'C']),
        genotype=(0, 1))
    example = self._example_for_variant(label.variant)
    with six.assertRaisesRegex(
        self, ValueError, 'Cannot add a non-confident label to an example'):
      self.processor.add_label_to_example(example, label)

  def _example_for_variant(self, variant):
    return tf_utils.make_example(variant, list(variant.alternate_bases),
                                 six.b('foo'), self.default_shape,
                                 self.default_format)

  @parameterized.parameters('sort_by_haplotypes', 'use_original_quality_scores')
  def test_flags_strictly_needs_sam_aux_fields(
      self, flags_strictly_needs_sam_aux_fields):
    FLAGS.mode = 'calling'
    FLAGS.ref = testdata.CHR20_FASTA
    FLAGS.reads = testdata.CHR20_BAM
    FLAGS.examples = 'examples.tfrecord'
    FLAGS[flags_strictly_needs_sam_aux_fields].value = True
    FLAGS.parse_sam_aux_fields = False

    with six.assertRaisesRegex(
        self, Exception,
        'If --{} is set then --parse_sam_aux_fields must be set too.'.format(
            flags_strictly_needs_sam_aux_fields)):
      make_examples.default_options(add_flags=True)

  @parameterized.parameters(
      ('add_hp_channel', True, None),
      ('add_hp_channel', False,
       'Note that --{} is set but --parse_sam_aux_fields is not set.'),
      ('add_hp_channel', None,
       'Because --{}=true, --parse_sam_aux_fields is set to true to enable '
       'reading auxiliary fields from reads.'),
  )
  def test_flag_optionally_needs_sam_aux_fields_with_different_parse_sam_aux_fields(
      self, flag_optionally_needs_sam_aux_fields, parse_sam_aux_fields,
      expected_message):
    FLAGS.mode = 'calling'
    FLAGS.ref = testdata.CHR20_FASTA
    FLAGS.reads = testdata.CHR20_BAM
    FLAGS.examples = 'examples.tfrecord'
    FLAGS[flag_optionally_needs_sam_aux_fields].value = True
    FLAGS.parse_sam_aux_fields = parse_sam_aux_fields

    with self.assertLogs() as logs:
      make_examples.default_options(add_flags=True)
    aux_fields_log_messages = [
        x for x in logs.output if '--parse_sam_aux_fields' in x
    ]
    if aux_fields_log_messages:
      self.assertRegex(
          aux_fields_log_messages[0],
          expected_message.format(flag_optionally_needs_sam_aux_fields))
    else:
      self.assertEmpty(aux_fields_log_messages)

  @parameterized.parameters(
      [
          dict(window_width=221),
          dict(window_width=1001),
      ],)
  def test_align_to_all_haplotypes(self, window_width):
    # align_to_all_haplotypes() will pull from the reference, so choose a
    # real variant.
    region = ranges.parse_literal('chr20:10,046,000-10,046,400')
    nist_reader = vcf.VcfReader(testdata.TRUTH_VARIANTS_VCF)
    nist_variants = list(nist_reader.query(region))
    # We picked this region to have exactly one known variant:
    # reference_bases: "AAGAAAGAAAG"
    # alternate_bases: "A", a deletion of 10 bp
    # start: 10046177
    # end: 10046188
    # reference_name: "chr20"

    variant = nist_variants[0]

    self.processor.pic = mock.Mock()
    self.processor.pic.width = window_width
    self.processor.pic.half_width = int((self.processor.pic.width - 1) / 2)

    self.processor.realigner = mock.Mock()
    # Using a real ref_reader to test that the reference allele matches
    # between the variant and the reference at the variant's coordinates.
    self.processor.realigner.ref_reader = self.ref_reader

    read = test_utils.make_read(
        'A' * 101, start=10046100, cigar='101M', quals=[30] * 101)

    self.processor.realigner.align_to_haplotype = mock.Mock()
    alt_info = self.processor.align_to_all_haplotypes(variant, [read])
    hap_alignments = alt_info['alt_alignments']
    hap_sequences = alt_info['alt_sequences']
    # Both outputs are keyed by alt allele.
    self.assertCountEqual(hap_alignments.keys(), ['A'])
    self.assertCountEqual(hap_sequences.keys(), ['A'])

    # Sequence must be the length of the window.
    self.assertLen(hap_sequences['A'], self.processor.pic.width)

    # align_to_haplotype should be called once for each alt (1 alt here).
    self.processor.realigner.align_to_haplotype.assert_called_once()

    # If variant reference_bases are wrong, it should raise a ValueError.
    variant.reference_bases = 'G'
    with six.assertRaisesRegex(self, ValueError,
                               'does not match the bases in the reference'):
      self.processor.align_to_all_haplotypes(variant, [read])


if __name__ == '__main__':
  absltest.main()
