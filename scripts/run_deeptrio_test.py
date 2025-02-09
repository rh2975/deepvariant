# Copyright 2019 Google LLC.
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
"""Tests for deepvariant .run_deeptrio."""

import io
from unittest import mock

from absl import flags
from absl.testing import absltest
from absl.testing import flagsaver
from absl.testing import parameterized
import six
from deepvariant.opensource_only.scripts import run_deeptrio

FLAGS = flags.FLAGS


# pylint: disable=line-too-long
class RunDeeptrioTest(parameterized.TestCase):

  def _create_all_commands_and_check_stdout(self, expected_stdout=None):
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
      commands, postprocess_cmds = run_deeptrio.create_all_commands(
          '/tmp/deeptrio_tmp_output')
      # Confirm that these basic commands don't have extra messages printed out
      # to stdout.
      if expected_stdout is None:
        self.assertEmpty(mock_stdout.getvalue())
      else:
        self.assertEqual(mock_stdout.getvalue(), expected_stdout)
    return commands, postprocess_cmds

  @parameterized.parameters('WGS', 'WES', 'PACBIO')
  @flagsaver.flagsaver
  def test_call_variants_postprocess_variants_commands(self, model_type):
    FLAGS.model_type = model_type
    FLAGS.ref = 'your_ref'
    FLAGS.reads_child = 'your_bam_child'
    FLAGS.reads_parent1 = 'your_bam_parent1'
    FLAGS.reads_parent2 = 'your_bam_parent2'
    FLAGS.sample_name_child = 'your_sample_child'
    FLAGS.sample_name_parent1 = 'your_sample_parent1'
    FLAGS.sample_name_parent2 = 'your_sample_parent2'
    FLAGS.output_vcf_child = 'your_vcf_child'
    FLAGS.output_vcf_parent1 = 'your_vcf_parent1'
    FLAGS.output_vcf_parent2 = 'your_vcf_parent2'
    FLAGS.output_gvcf_child = 'your_gvcf_child'
    FLAGS.output_gvcf_parent1 = 'your_gvcf_parent1'
    FLAGS.output_gvcf_parent2 = 'your_gvcf_parent2'
    FLAGS.output_gvcf_merged = 'your_gvcf_merged'
    FLAGS.num_shards = 64
    commands, postprocess_cmds = self._create_all_commands_and_check_stdout()

    self.assertEqual(
        commands[1], 'time /opt/deepvariant/bin/call_variants '
        '--outfile '
        '"/tmp/deeptrio_tmp_output/call_variants_output_child.tfrecord.gz" '
        '--examples "/tmp/deeptrio_tmp_output/make_examples_child.tfrecord@64.gz" '
        '--checkpoint "/opt/models/deeptrio/{}/child/model.ckpt"'.format(
            model_type.lower()))
    self.assertEqual(
        commands[2], 'time /opt/deepvariant/bin/call_variants '
        '--outfile '
        '"/tmp/deeptrio_tmp_output/call_variants_output_parent1.tfrecord.gz" '
        '--examples "/tmp/deeptrio_tmp_output/make_examples_parent1.tfrecord@64.gz" '
        '--checkpoint "/opt/models/deeptrio/{}/parent/model.ckpt"'.format(
            model_type.lower()))
    self.assertEqual(
        commands[3], 'time /opt/deepvariant/bin/call_variants '
        '--outfile '
        '"/tmp/deeptrio_tmp_output/call_variants_output_parent2.tfrecord.gz" '
        '--examples "/tmp/deeptrio_tmp_output/make_examples_parent2.tfrecord@64.gz" '
        '--checkpoint "/opt/models/deeptrio/{}/parent/model.ckpt"'.format(
            model_type.lower()))
    self.assertEqual(
        postprocess_cmds[0], 'time /opt/deepvariant/bin/postprocess_variants '
        '--ref "your_ref" '
        '--infile '
        '"/tmp/deeptrio_tmp_output/call_variants_output_child.tfrecord.gz" '
        '--outfile "your_vcf_child" '
        '--nonvariant_site_tfrecord_path '
        '"/tmp/deeptrio_tmp_output/gvcf_child.tfrecord@64.gz" '
        '--gvcf_outfile "your_gvcf_child"')
    self.assertEqual(
        postprocess_cmds[1], 'time /opt/deepvariant/bin/postprocess_variants '
        '--ref "your_ref" '
        '--infile '
        '"/tmp/deeptrio_tmp_output/call_variants_output_parent1.tfrecord.gz" '
        '--outfile "your_vcf_parent1" '
        '--nonvariant_site_tfrecord_path '
        '"/tmp/deeptrio_tmp_output/gvcf_parent1.tfrecord@64.gz" '
        '--gvcf_outfile "your_gvcf_parent1"')
    self.assertEqual(
        postprocess_cmds[2], 'time /opt/deepvariant/bin/postprocess_variants '
        '--ref "your_ref" '
        '--infile '
        '"/tmp/deeptrio_tmp_output/call_variants_output_parent2.tfrecord.gz" '
        '--outfile "your_vcf_parent2" '
        '--nonvariant_site_tfrecord_path '
        '"/tmp/deeptrio_tmp_output/gvcf_parent2.tfrecord@64.gz" '
        '--gvcf_outfile "your_gvcf_parent2"')
    self.assertLen(commands, 4)
    self.assertLen(postprocess_cmds, 3)

  @parameterized.parameters('WGS', 'WES', 'PACBIO')
  @flagsaver.flagsaver
  def test_duo_call_variants_postprocess_variants_commands(self, model_type):
    FLAGS.model_type = model_type
    FLAGS.ref = 'your_ref'
    FLAGS.reads_child = 'your_bam_child'
    FLAGS.reads_parent1 = 'your_bam_parent1'
    FLAGS.sample_name_child = 'your_sample_child'
    FLAGS.sample_name_parent1 = 'your_sample_parent1'
    FLAGS.output_vcf_child = 'your_vcf_child'
    FLAGS.output_vcf_parent1 = 'your_vcf_parent1'
    FLAGS.output_gvcf_child = 'your_gvcf_child'
    FLAGS.output_gvcf_parent1 = 'your_gvcf_parent1'
    FLAGS.output_gvcf_merged = 'your_gvcf_merged'
    FLAGS.num_shards = 64
    commands, postprocess_cmds = self._create_all_commands_and_check_stdout()

    self.assertEqual(
        commands[1], 'time /opt/deepvariant/bin/call_variants '
        '--outfile '
        '"/tmp/deeptrio_tmp_output/call_variants_output_child.tfrecord.gz" '
        '--examples "/tmp/deeptrio_tmp_output/make_examples_child.tfrecord@64.gz" '
        '--checkpoint "/opt/models/deeptrio/{}/child/model.ckpt"'.format(
            model_type.lower()))
    self.assertEqual(
        commands[2], 'time /opt/deepvariant/bin/call_variants '
        '--outfile '
        '"/tmp/deeptrio_tmp_output/call_variants_output_parent1.tfrecord.gz" '
        '--examples "/tmp/deeptrio_tmp_output/make_examples_parent1.tfrecord@64.gz" '
        '--checkpoint "/opt/models/deeptrio/{}/parent/model.ckpt"'.format(
            model_type.lower()))
    self.assertEqual(
        postprocess_cmds[0], 'time /opt/deepvariant/bin/postprocess_variants '
        '--ref "your_ref" '
        '--infile '
        '"/tmp/deeptrio_tmp_output/call_variants_output_child.tfrecord.gz" '
        '--outfile "your_vcf_child" '
        '--nonvariant_site_tfrecord_path '
        '"/tmp/deeptrio_tmp_output/gvcf_child.tfrecord@64.gz" '
        '--gvcf_outfile "your_gvcf_child"')
    self.assertEqual(
        postprocess_cmds[1], 'time /opt/deepvariant/bin/postprocess_variants '
        '--ref "your_ref" '
        '--infile '
        '"/tmp/deeptrio_tmp_output/call_variants_output_parent1.tfrecord.gz" '
        '--outfile "your_vcf_parent1" '
        '--nonvariant_site_tfrecord_path '
        '"/tmp/deeptrio_tmp_output/gvcf_parent1.tfrecord@64.gz" '
        '--gvcf_outfile "your_gvcf_parent1"')
    # pylint: disable=g-generic-assert
    self.assertLen(commands, 3)
    self.assertLen(postprocess_cmds, 2)

  @parameterized.parameters(
      ('WGS', '--gvcf "/tmp/deeptrio_tmp_output/gvcf.tfrecord@64.gz" '
       '--pileup_image_height_child "60" '
       '--pileup_image_height_parent "40" '),
      ('WES', '--gvcf "/tmp/deeptrio_tmp_output/gvcf.tfrecord@64.gz" '
       '--pileup_image_height_child "100" '
       '--pileup_image_height_parent "100" '),
      ('PACBIO', '--add_hp_channel '
       '--alt_aligned_pileup "diff_channels" '
       '--gvcf "/tmp/deeptrio_tmp_output/gvcf.tfrecord@64.gz" '
       '--noparse_sam_aux_fields '
       '--pileup_image_height_child "60" '
       '--pileup_image_height_parent "40" '
       '--pileup_image_width "199" '
       '--norealign_reads '
       '--nosort_by_haplotypes '
       '--vsc_min_fraction_indels "0.12" '))
  @flagsaver.flagsaver
  def test_make_examples_commands_with_types(self, model_type,
                                             extra_args_plus_gvcf):
    FLAGS.model_type = model_type
    FLAGS.ref = 'your_ref'
    FLAGS.reads_child = 'your_bam_child'
    FLAGS.reads_parent1 = 'your_bam_parent1'
    FLAGS.reads_parent2 = 'your_bam_parent2'
    FLAGS.sample_name_child = 'your_sample_child'
    FLAGS.sample_name_parent1 = 'your_sample_parent1'
    FLAGS.sample_name_parent2 = 'your_sample_parent2'
    FLAGS.output_vcf_child = 'your_vcf_child'
    FLAGS.output_vcf_parent1 = 'your_vcf_parent1'
    FLAGS.output_vcf_parent2 = 'your_vcf_parent2'
    FLAGS.output_gvcf_child = 'your_gvcf_child'
    FLAGS.output_gvcf_parent1 = 'your_gvcf_parent1'
    FLAGS.output_gvcf_parent2 = 'your_gvcf_parent2'
    FLAGS.output_gvcf_merged = 'your_gvcf_merged'
    FLAGS.num_shards = 64
    commands, _ = self._create_all_commands_and_check_stdout()
    self.assertEqual(
        commands[0], 'time seq 0 63 '
        '| parallel -q --halt 2 --line-buffer '
        '/opt/deepvariant/bin/deeptrio/make_examples '
        '--mode calling '
        '--ref "your_ref" '
        '--reads_parent1 "your_bam_parent1" '
        '--reads_parent2 "your_bam_parent2" '
        '--reads "your_bam_child" '
        '--examples "/tmp/deeptrio_tmp_output/make_examples.tfrecord@64.gz" '
        '--sample_name "your_sample_child" '
        '--sample_name_parent1 "your_sample_parent1" '
        '--sample_name_parent2 "your_sample_parent2" '
        '%s'
        '--task {}' % extra_args_plus_gvcf)

  @parameterized.parameters(
      ('WGS', '--gvcf "/tmp/deeptrio_tmp_output/gvcf.tfrecord@64.gz" '
       '--pileup_image_height_child "60" '
       '--pileup_image_height_parent "40" '),
      ('WES', '--gvcf "/tmp/deeptrio_tmp_output/gvcf.tfrecord@64.gz" '
       '--pileup_image_height_child "100" '
       '--pileup_image_height_parent "100" '),
      ('PACBIO', '--add_hp_channel '
       '--alt_aligned_pileup "diff_channels" '
       '--gvcf "/tmp/deeptrio_tmp_output/gvcf.tfrecord@64.gz" '
       '--noparse_sam_aux_fields '
       '--pileup_image_height_child "60" '
       '--pileup_image_height_parent "40" '
       '--pileup_image_width "199" '
       '--norealign_reads '
       '--nosort_by_haplotypes '
       '--vsc_min_fraction_indels "0.12" '))
  @flagsaver.flagsaver
  def test_duo_make_examples_commands_with_types(self, model_type,
                                                 extra_args_plus_gvcf):
    FLAGS.model_type = model_type
    FLAGS.ref = 'your_ref'
    FLAGS.reads_child = 'your_bam_child'
    FLAGS.reads_parent1 = 'your_bam_parent1'
    FLAGS.sample_name_child = 'your_sample_child'
    FLAGS.sample_name_parent1 = 'your_sample_parent1'
    FLAGS.output_vcf_child = 'your_vcf_child'
    FLAGS.output_vcf_parent1 = 'your_vcf_parent1'
    FLAGS.output_gvcf_child = 'your_gvcf_child'
    FLAGS.output_gvcf_parent1 = 'your_gvcf_parent1'
    FLAGS.output_gvcf_merged = 'your_gvcf_merged'
    FLAGS.num_shards = 64
    commands, _ = self._create_all_commands_and_check_stdout()
    self.assertEqual(
        commands[0], 'time seq 0 63 '
        '| parallel -q --halt 2 --line-buffer '
        '/opt/deepvariant/bin/deeptrio/make_examples '
        '--mode calling '
        '--ref "your_ref" '
        '--reads_parent1 "your_bam_parent1" '
        '--reads "your_bam_child" '
        '--examples "/tmp/deeptrio_tmp_output/make_examples.tfrecord@64.gz" '
        '--sample_name "your_sample_child" '
        '--sample_name_parent1 "your_sample_parent1" '
        '%s'
        '--task {}' % extra_args_plus_gvcf)

  @parameterized.parameters(
      (None, '--add_hp_channel '
       '--alt_aligned_pileup "diff_channels" '
       '--gvcf "/tmp/deeptrio_tmp_output/gvcf.tfrecord@64.gz" '
       '--noparse_sam_aux_fields '
       '--pileup_image_height_child "60" '
       '--pileup_image_height_parent "40" '
       '--pileup_image_width "199" '
       '--norealign_reads '
       '--nosort_by_haplotypes '
       '--vsc_min_fraction_indels "0.12" ', None),
      ('alt_aligned_pileup="rows",vsc_min_fraction_indels=0.03',
       '--add_hp_channel '
       '--alt_aligned_pileup "rows" '
       '--gvcf "/tmp/deeptrio_tmp_output/gvcf.tfrecord@64.gz" '
       '--noparse_sam_aux_fields '
       '--pileup_image_height_child "60" '
       '--pileup_image_height_parent "40" '
       '--pileup_image_width "199" '
       '--norealign_reads '
       '--nosort_by_haplotypes '
       '--vsc_min_fraction_indels "0.03" ',
       '\nWarning: --alt_aligned_pileup is previously set to diff_channels, '
       'now to "rows".\n'
       '\nWarning: --vsc_min_fraction_indels is previously set to 0.12, '
       'now to 0.03.\n'),
  )
  @flagsaver.flagsaver
  def test_pacbio_args_overwrite(self, make_examples_extra_args, expected_args,
                                 expected_stdout):
    """Confirms that adding extra flags can overwrite the default from mode."""
    FLAGS.model_type = 'PACBIO'
    FLAGS.ref = 'your_ref'
    FLAGS.sample_name_child = 'your_sample_child'
    FLAGS.sample_name_parent1 = 'your_sample_parent1'
    FLAGS.sample_name_parent2 = 'your_sample_parent2'
    FLAGS.reads_child = 'your_bam_child'
    FLAGS.reads_parent1 = 'your_bam_parent1'
    FLAGS.reads_parent2 = 'your_bam_parent2'
    FLAGS.output_vcf_child = 'your_vcf_child'
    FLAGS.output_vcf_parent1 = 'your_vcf_parent1'
    FLAGS.output_vcf_parent2 = 'your_vcf_parent2'
    FLAGS.output_gvcf_child = 'your_gvcf_child'
    FLAGS.output_gvcf_parent1 = 'your_gvcf_parent1'
    FLAGS.output_gvcf_parent2 = 'your_gvcf_parent2'
    FLAGS.num_shards = 64
    FLAGS.regions = None
    FLAGS.make_examples_extra_args = make_examples_extra_args
    commands, _ = self._create_all_commands_and_check_stdout(expected_stdout)
    self.assertEqual(
        commands[0], 'time seq 0 63 | parallel -q --halt 2 --line-buffer '
        '/opt/deepvariant/bin/deeptrio/make_examples --mode calling '
        '--ref "your_ref" --reads_parent1 "your_bam_parent1" '
        '--reads_parent2 "your_bam_parent2" '
        '--reads "your_bam_child" '
        '--examples "/tmp/deeptrio_tmp_output/make_examples.tfrecord@64.gz" '
        '--sample_name "your_sample_child" '
        '--sample_name_parent1 "your_sample_parent1" '
        '--sample_name_parent2 "your_sample_parent2" '
        '%s'
        '--task {}' % expected_args)

  @parameterized.parameters(
      (None, ('sort_by_haplotypes=true,parse_sam_aux_fields=true'), True),
      (True, ('sort_by_haplotypes=true,parse_sam_aux_fields=true'), False),
  )
  @flagsaver.flagsaver
  def test_use_hp_information_conflicts(self, use_hp_information,
                                        make_examples_extra_args, has_conflict):
    """Confirms that PacBio use_hp_information can conflict with HP args."""
    FLAGS.model_type = 'PACBIO'
    FLAGS.ref = 'your_ref'
    FLAGS.sample_name_child = 'your_sample_child'
    FLAGS.sample_name_parent1 = 'your_sample_parent1'
    FLAGS.sample_name_parent2 = 'your_sample_parent2'
    FLAGS.reads_child = 'your_bam_child'
    FLAGS.reads_parent1 = 'your_bam_parent1'
    FLAGS.reads_parent2 = 'your_bam_parent2'
    FLAGS.output_vcf_child = 'your_vcf_child'
    FLAGS.output_vcf_parent1 = 'your_vcf_parent1'
    FLAGS.output_vcf_parent2 = 'your_vcf_parent2'
    FLAGS.output_gvcf_child = 'your_gvcf_child'
    FLAGS.output_gvcf_parent1 = 'your_gvcf_parent1'
    FLAGS.output_gvcf_parent2 = 'your_gvcf_parent2'
    FLAGS.num_shards = 64
    FLAGS.regions = None
    FLAGS.use_hp_information = use_hp_information
    FLAGS.make_examples_extra_args = make_examples_extra_args
    if has_conflict:
      with six.assertRaisesRegex(self, ValueError,
                                 'conflicts with other flags'):
        run_deeptrio.create_all_commands('/tmp/deeptrio_tmp_output')
    else:
      # Otherwise, the command should run without rasing errors.
      run_deeptrio.create_all_commands('/tmp/deeptrio_tmp_output')

  @parameterized.parameters('WGS', 'WES')
  @flagsaver.flagsaver
  def test_use_hp_information_only_with_pacbio(self, model_type):
    """Confirms use_hp_information only works for."""
    FLAGS.model_type = model_type
    FLAGS.ref = 'your_ref'
    FLAGS.sample_name_child = 'your_sample_child'
    FLAGS.sample_name_parent1 = 'your_sample_parent1'
    FLAGS.sample_name_parent2 = 'your_sample_parent2'
    FLAGS.reads_child = 'your_bam_child'
    FLAGS.reads_parent1 = 'your_bam_parent1'
    FLAGS.reads_parent2 = 'your_bam_parent2'
    FLAGS.output_vcf_child = 'your_vcf_child'
    FLAGS.output_vcf_parent1 = 'your_vcf_parent1'
    FLAGS.output_vcf_parent2 = 'your_vcf_parent2'
    FLAGS.output_gvcf_child = 'your_gvcf_child'
    FLAGS.output_gvcf_parent1 = 'your_gvcf_parent1'
    FLAGS.output_gvcf_parent2 = 'your_gvcf_parent2'
    FLAGS.num_shards = 64
    FLAGS.regions = None
    FLAGS.use_hp_information = True
    with six.assertRaisesRegex(
        self, ValueError, '--use_hp_information can only be used with '
        '--model_type="PACBIO"'):
      run_deeptrio.create_all_commands('/tmp/deeptrio_tmp_output')

  @parameterized.parameters(
      ('chr1:20-30', '--pileup_image_height_child "60" '
       '--pileup_image_height_parent "40" '
       '--regions "chr1:20-30"'),
      ('chr1:20-30 chr2:100-200', '--pileup_image_height_child "60" '
       '--pileup_image_height_parent "40" '
       '--regions "chr1:20-30 chr2:100-200"'),
      ("'chr1:20-30 chr2:100-200'", '--pileup_image_height_child "60" '
       '--pileup_image_height_parent "40" '
       "--regions 'chr1:20-30 chr2:100-200'"),
  )
  def test_make_examples_regions(self, regions, expected_args):
    FLAGS.model_type = 'WGS'
    FLAGS.ref = 'your_ref'
    FLAGS.sample_name_child = 'your_sample_child'
    FLAGS.sample_name_parent1 = 'your_sample_parent1'
    FLAGS.sample_name_parent2 = 'your_sample_parent2'
    FLAGS.reads_child = 'your_bam_child'
    FLAGS.reads_parent1 = 'your_bam_parent1'
    FLAGS.reads_parent2 = 'your_bam_parent2'
    FLAGS.output_vcf_child = 'your_vcf_child'
    FLAGS.output_vcf_parent1 = 'your_vcf_parent1'
    FLAGS.output_vcf_parent2 = 'your_vcf_parent2'
    FLAGS.num_shards = 64
    FLAGS.regions = regions
    commands, _ = self._create_all_commands_and_check_stdout()

    self.assertEqual(
        commands[0], 'time seq 0 63 | parallel -q --halt 2 --line-buffer '
        '/opt/deepvariant/bin/deeptrio/make_examples --mode calling '
        '--ref "your_ref" --reads_parent1 "your_bam_parent1" '
        '--reads_parent2 "your_bam_parent2" '
        '--reads "your_bam_child" '
        '--examples "/tmp/deeptrio_tmp_output/make_examples.tfrecord@64.gz" '
        '--sample_name "your_sample_child" '
        '--sample_name_parent1 "your_sample_parent1" '
        '--sample_name_parent2 "your_sample_parent2" '
        '%s '
        '--task {}' % expected_args)

  @flagsaver.flagsaver
  def test_make_examples_extra_args_invalid(self):
    FLAGS.model_type = 'WGS'
    FLAGS.ref = 'your_ref'
    FLAGS.sample_name_child = 'your_sample_child'
    FLAGS.sample_name_parent1 = 'your_sample_parent1'
    FLAGS.sample_name_parent2 = 'your_sample_parent2'
    FLAGS.reads_child = 'your_bam_child'
    FLAGS.reads_parent1 = 'your_bam_parent1'
    FLAGS.reads_parent2 = 'your_bam_parent2'
    FLAGS.output_vcf_child = 'your_vcf_child'
    FLAGS.output_vcf_parent1 = 'your_vcf_parent1'
    FLAGS.output_vcf_parent2 = 'your_vcf_parent2'
    FLAGS.output_gvcf_child = 'your_gvcf_child'
    FLAGS.output_gvcf_parent1 = 'your_gvcf_parent1'
    FLAGS.output_gvcf_parent2 = 'your_gvcf_parent2'
    FLAGS.num_shards = 64
    FLAGS.make_examples_extra_args = 'keep_secondary_alignments'
    with six.assertRaisesRegex(self, ValueError, 'not enough values to unpack'):
      _, _ = run_deeptrio.create_all_commands('/tmp/deeptrio_tmp_output')

  @parameterized.parameters(
      ('batch_size=1024', '--batch_size "1024"'),
      ('batch_size=4096,'
       'config_string="gpu_options: {per_process_gpu_memory_fraction: 0.5}"',
       '--batch_size "4096" '
       '--config_string "gpu_options: {per_process_gpu_memory_fraction: 0.5}"'),
  )
  @flagsaver.flagsaver
  def test_call_variants_extra_args(self, call_variants_extra_args,
                                    expected_args):
    FLAGS.model_type = 'WGS'
    FLAGS.ref = 'your_ref'
    FLAGS.sample_name_child = 'your_sample_child'
    FLAGS.sample_name_parent1 = 'your_sample_parent1'
    FLAGS.sample_name_parent2 = 'your_sample_parent2'
    FLAGS.reads_child = 'your_bam_child'
    FLAGS.reads_parent1 = 'your_bam_parent1'
    FLAGS.reads_parent2 = 'your_bam_parent2'
    FLAGS.output_vcf_child = 'your_vcf_child'
    FLAGS.output_vcf_parent1 = 'your_vcf_parent1'
    FLAGS.output_vcf_parent2 = 'your_vcf_parent2'
    FLAGS.output_gvcf_child = 'your_gvcf_child'
    FLAGS.output_gvcf_parent1 = 'your_gvcf_parent1'
    FLAGS.output_gvcf_parent2 = 'your_gvcf_parent2'
    FLAGS.num_shards = 64
    FLAGS.call_variants_extra_args = call_variants_extra_args
    commands, _ = self._create_all_commands_and_check_stdout()

    self.assertEqual(
        commands[1], 'time /opt/deepvariant/bin/call_variants '
        '--outfile '
        '"/tmp/deeptrio_tmp_output/call_variants_output_child.tfrecord.gz" '
        '--examples "/tmp/deeptrio_tmp_output/make_examples_child.tfrecord@64.gz" '
        '--checkpoint "/opt/models/deeptrio/wgs/child/model.ckpt" '
        '%s' % expected_args)

  @parameterized.parameters(
      ('qual_filter=3.0', '--qual_filter "3.0"'),)
  @flagsaver.flagsaver
  def test_postprocess_variants_extra_args(self,
                                           postprocess_variants_extra_args,
                                           expected_args):
    FLAGS.model_type = 'WGS'
    FLAGS.ref = 'your_ref'
    FLAGS.sample_name_child = 'your_sample_child'
    FLAGS.sample_name_parent1 = 'your_sample_parent1'
    FLAGS.sample_name_parent2 = 'your_sample_parent2'
    FLAGS.reads_child = 'your_bam_child'
    FLAGS.reads_parent1 = 'your_bam_parent1'
    FLAGS.reads_parent2 = 'your_bam_parent2'
    FLAGS.output_vcf_child = 'your_vcf_child'
    FLAGS.output_vcf_parent1 = 'your_vcf_parent1'
    FLAGS.output_vcf_parent2 = 'your_vcf_parent2'
    FLAGS.output_gvcf_child = 'your_gvcf_child'
    FLAGS.output_gvcf_parent1 = 'your_gvcf_parent1'
    FLAGS.output_gvcf_parent2 = 'your_gvcf_parent2'
    FLAGS.num_shards = 64
    FLAGS.postprocess_variants_extra_args = postprocess_variants_extra_args
    _, commands_post_process = self._create_all_commands_and_check_stdout()

    self.assertEqual(
        commands_post_process[0],
        'time /opt/deepvariant/bin/postprocess_variants '
        '--ref "your_ref" '
        '--infile '
        '"/tmp/deeptrio_tmp_output/call_variants_output_child.tfrecord.gz" '
        '--outfile "your_vcf_child" '
        '--nonvariant_site_tfrecord_path '
        '"/tmp/deeptrio_tmp_output/gvcf_child.tfrecord@64.gz" '
        '--gvcf_outfile "your_gvcf_child" '
        '%s' % expected_args)

  @parameterized.parameters(
      (True, 'vcf_stats_report=true', '--vcf_stats_report'),
      (True, 'vcf_stats_report=false', '--novcf_stats_report'),
      # These two cases demonstrate we might end up havig duplicated and
      # potentially conflicting flags when using *extra_args.
      (False, 'vcf_stats_report=true', '--novcf_stats_report --vcf_stats_report'
      ),
      (False, 'vcf_stats_report=false',
       '--novcf_stats_report --novcf_stats_report'),
  )
  @flagsaver.flagsaver
  def test_postprocess_variants_duplicate_extra_args(
      self, vcf_stats_report, postprocess_variants_extra_args,
      expected_vcf_stats_report):
    FLAGS.model_type = 'WGS'
    FLAGS.ref = 'your_ref'
    FLAGS.sample_name_child = 'your_sample_child'
    FLAGS.sample_name_parent1 = 'your_sample_parent1'
    FLAGS.sample_name_parent2 = 'your_sample_parent2'
    FLAGS.reads_child = 'your_bam_child'
    FLAGS.reads_parent1 = 'your_bam_parent1'
    FLAGS.reads_parent2 = 'your_bam_parent2'
    FLAGS.output_vcf_child = 'your_vcf_child'
    FLAGS.output_vcf_parent1 = 'your_vcf_parent1'
    FLAGS.output_vcf_parent2 = 'your_vcf_parent2'
    FLAGS.output_gvcf_child = 'your_gvcf_child'
    FLAGS.output_gvcf_parent1 = 'your_gvcf_parent1'
    FLAGS.output_gvcf_parent2 = 'your_gvcf_parent2'
    FLAGS.num_shards = 64
    FLAGS.vcf_stats_report = vcf_stats_report
    FLAGS.postprocess_variants_extra_args = postprocess_variants_extra_args
    _, commands_post_process = run_deeptrio.create_all_commands(
        '/tmp/deeptrio_tmp_output')

    self.assertEqual(
        commands_post_process[0],
        'time /opt/deepvariant/bin/postprocess_variants '
        '--ref "your_ref" '
        '--infile '
        '"/tmp/deeptrio_tmp_output/call_variants_output_child.tfrecord.gz" '
        '--outfile "your_vcf_child" '
        '--nonvariant_site_tfrecord_path '
        '"/tmp/deeptrio_tmp_output/gvcf_child.tfrecord@64.gz" '
        '--gvcf_outfile "your_gvcf_child" '
        '%s' % expected_vcf_stats_report)

if __name__ == '__main__':
  absltest.main()
